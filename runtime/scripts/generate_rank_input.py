#!/usr/bin/env python3
"""Generate deterministic security-scan worklists.

This script stays deliberately model-free:

- `make-repo-scope-input` lists every explicitly scoped repository file.
- `make-diff-rank-input` creates the deterministic diff-scoped JSONL candidate
  worklist from Git changed paths. It supports committed revision diffs and
  local working-tree patches.

Candidate selection uses repository scope, native tool ignore rules, and binary detection,
not filename or directory classifications. Diff inputs use bounded source previews.
"""

# Upstream deleted generate_rank_input.py in 0.7.0 (05cceee24, "run inventory and
# ranking helpers in Node") and moved these two subcommands into its TypeScript MCP
# launcher (`--helper make-repo-scope-input` / `--helper make-diff-rank-input`,
# implemented in mcp-app/src/helpers/generate-inventory.ts and inventory-git.ts),
# which this port does not vendor. This carried copy is the last upstream Python
# version brought in line with that implementation:
#   - Git runs through the vendored trusted, sanitised workbench_target.git_command.
#   - A changed working file that is no longer a regular file is skipped instead of
#     being emitted with an empty preview; one reached through a directory link is
#     kept without a preview.
#   - Committed blobs and working files share one sampler: binary content is detected
#     across every byte, previews come from the first 64 KiB.
#   - Rows are de-duplicated by path and sorted by code point; --preview-bytes must be
#     a plain integer (zero or negative yields empty previews).
# The other subcommands upstream retired earlier stay retired here. The CLI is unchanged.

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# Some plugin hosts launch Python with safe-path isolation enabled.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_in_scope_files import (
    InventoryError,
    changed_paths,
    contained,
    diff_samples,
    regular,
    windows_stream_component,
)
from rank_preview import DEFAULT_PREVIEW_BYTES, preview_for_bytes, sample_file
from workbench_target import SOURCE_METADATA_DIRECTORIES, git_directory_snapshot_paths

JsonRow = dict[str, object]
INTEGER = re.compile(r"[+-]?[0-9]+")


def preview_bytes(value: str) -> int:
    text = value.strip()
    if not INTEGER.fullmatch(text):
        raise argparse.ArgumentTypeError("--preview-bytes must be an integer")
    return int(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Security scan worklist helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scoped = subparsers.add_parser(
        "make-repo-scope-input",
        help="List every explicitly scoped file without ranking or reading its contents.",
    )
    scoped.add_argument("--repo", required=True, help="Repository root.")
    scoped.add_argument(
        "--scopes-file",
        required=True,
        help="JSON array of repository-relative files and directories to scan together.",
    )
    scoped.add_argument("--out", required=True, help="Output scoped-source-input.jsonl path.")

    diff = subparsers.add_parser(
        "make-diff-rank-input",
        help="Create rank_input.jsonl from Git changed text files.",
    )
    diff.add_argument("--repo", required=True, help="Repository root.")
    diff.add_argument("--base", required=True, help="Git diff base revision.")
    diff.add_argument(
        "--mode",
        choices=("revisions", "local-patch"),
        default="revisions",
        help="Git diff mode: committed revisions or staged plus unstaged local patch.",
    )
    diff.add_argument("--head", default="HEAD", help="Git diff head revision.")
    diff.add_argument("--out", required=True, help="Output rank_input.jsonl path.")
    diff.add_argument("--area", default="diff", help="Area label for changed-file rows.")
    diff.add_argument(
        "--preview-bytes",
        type=preview_bytes,
        default=DEFAULT_PREVIEW_BYTES,
        help=f"Maximum UTF-8 bytes in each preview. Defaults to {DEFAULT_PREVIEW_BYTES}.",
    )

    return parser.parse_args()


def resolve_repo(value: str) -> Path:
    try:
        repo = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise SystemExit(f"Repo path not found: {Path(value).expanduser()}")
    if not repo.is_dir():
        raise SystemExit(f"Repo path not found: {repo}")
    return repo


def lexical_path(path: str) -> str:
    """Drop empty and '.' components without collapsing symlink-sensitive '..'."""
    prefix = "//" if path.startswith("//") and not path.startswith("///") else "/" if path.startswith("/") else ""
    return prefix + "/".join(part for part in path.split("/") if part and part != ".") or "."


def resolve_scope(repo: Path, scope: str) -> Path:
    """Resolve an explicit scope literally: no home expansion, no globbing."""
    scope_path = Path(lexical_path(scope) if os.name != "nt" else scope)
    stream = windows_stream_component(scope_path)
    if stream is not None:
        raise SystemExit(f"Scope must not use an NTFS alternate data stream: {stream}")
    if not scope_path.is_absolute():
        scope_path = repo / scope_path
    try:
        relative = scope_path.relative_to(repo)
    except ValueError as exc:
        raise SystemExit(f"Scope must be inside repo: {scope_path}") from exc
    # Do not normalise away a link before checking link/.. scopes.
    ancestor = repo
    for part in relative.parts:
        if part == "..":
            if ancestor == repo:
                raise SystemExit(f"Scope must be inside repo: {scope_path}")
            ancestor = ancestor.parent
            continue
        ancestor /= part
        try:
            metadata = ancestor.stat(follow_symlinks=False)
        except OSError as exc:
            raise SystemExit(f"Scope path not found: {ancestor}") from exc
        if ancestor.is_symlink() or getattr(metadata, "st_reparse_tag", 0) & 0x20000000:
            raise SystemExit(f"Requested scope must not contain symbolic links: {ancestor}")
    try:
        scope_path = scope_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"Scope path not found: {scope_path}") from exc
    try:
        scope_path.relative_to(repo)
    except ValueError as exc:
        raise SystemExit(f"Scope must be inside repo: {scope_path}") from exc
    if not scope_path.is_dir() and not scope_path.is_file():
        raise SystemExit(f"Scope path not found: {scope_path}")
    return scope_path


def write_jsonl(output: Path, rows: list[JsonRow]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        for row in rows:
            # ensure_ascii escapes DEL, every non-ASCII unit and U+2028/U+2029.
            handle.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")))
            handle.write("\r\n" if os.name == "nt" else "\n")


def load_scopes_file(scopes_file: Path) -> list[str]:
    try:
        loaded: object = json.loads(scopes_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to read scopes file: {scopes_file}") from exc
    if (
        not isinstance(loaded, list)
        or not loaded
        or any(not isinstance(scope, str) or not scope for scope in loaded)
    ):
        raise SystemExit(f"Scopes file must contain a non-empty JSON string array: {scopes_file}")
    return loaded


def scope_candidates(repo: Path, scope_path: Path) -> Iterable[Path]:
    """Use Git's inventory in worktrees and ripgrep's ignore rules elsewhere.

    Git retains tracked files and applies its standard exclusions to untracked files.
    Outside Git, ripgrep also honors .ignore and .rgignore alongside .gitignore.
    Explicit file scopes bypass directory ignore rules.
    """
    if scope_path.is_file():
        return (scope_path,)
    git_candidates = git_directory_snapshot_paths(scope_path)
    if git_candidates is not None:
        return git_candidates

    command = [
        "rg",
        "--files",
        "--hidden",
        "--no-require-git",
        "--null",
        # Also exclude descendants when the scope starts inside metadata.
        "--glob",
        "!**/{.git,.svn}",
        "--glob",
        "!**/{.git,.svn}/**",
        "--",
        scope_path.relative_to(repo).as_posix() or ".",
    ]
    try:
        result = subprocess.run(command, cwd=repo, capture_output=True, check=False)
    except OSError as exc:
        ignore_names = (".gitignore", ".ignore", ".rgignore")
        ancestors = (scope_path, *scope_path.parents)
        has_ignore_rules = (
            any(os.path.lexists(ancestor / ".git") for ancestor in (repo, *repo.parents))
            or any(
                (ancestor / name).is_file()
                for ancestor in ancestors
                if ancestor == repo or repo in ancestor.parents
                for name in ignore_names
            )
            or any(path.name in ignore_names for path in scope_path.rglob("*") if path.is_file())
        )
        if has_ignore_rules:
            raise SystemExit(
                "Could not safely enumerate ignored scoped files without Git or ripgrep."
            ) from exc
        return scope_path.rglob("*")

    if result.returncode not in (0, 1):
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        signal_note = f" (signal {-result.returncode})" if result.returncode < 0 else ""
        raise SystemExit(f"Could not enumerate scoped repository files{signal_note}: {detail}")
    return (repo / os.fsdecode(path) for path in result.stdout.split(b"\0") if path)


def make_repo_scope_input(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    scopes = load_scopes_file(Path(args.scopes_file).expanduser())
    resolved = [resolve_scope(repo, scope) for scope in scopes]
    rows_by_path: dict[str, JsonRow] = {}
    for scope_path in resolved:
        for path in scope_candidates(repo, scope_path):
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.resolve(strict=True).relative_to(repo)
            except (OSError, RuntimeError, ValueError):
                continue
            if not SOURCE_METADATA_DIRECTORIES.isdisjoint(relative.parts):
                continue
            rows_by_path.setdefault(relative.as_posix(), {"path": relative.as_posix()})

    rows = [rows_by_path[name] for name in sorted(rows_by_path)]
    output = Path(args.out).expanduser()
    write_jsonl(output, rows)
    print(f"Wrote {len(rows)} scoped paths to {output}")


def make_diff_rank_input(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    try:
        changes = changed_paths(repo, args.base, args.head, args.mode)
        samples = diff_samples(repo, args.base, args.head, args.mode, changes)
    except InventoryError as error:
        raise SystemExit(str(error)) from error

    rows_by_path: dict[str, JsonRow] = {}
    for name, status in changes:
        preview = ""
        if name in samples:
            content, is_binary = samples[name]
            if is_binary:
                continue
            if status != "D":
                preview, _ = preview_for_bytes(content, args.preview_bytes)
        else:
            path = repo / name
            if not regular(path):
                continue
            if contained(repo, path):
                content, is_binary = sample_file(path)
                if is_binary:
                    continue
                preview, _ = preview_for_bytes(content, args.preview_bytes)
        rows_by_path[name] = {"path": name, "area": args.area, "preview": preview}

    rows = [rows_by_path[name] for name in sorted(rows_by_path)]
    output = Path(args.out).expanduser()
    write_jsonl(output, rows)
    print(f"Wrote {len(rows)} rows to {output}")


def main() -> None:
    args = parse_args()
    if args.command == "make-repo-scope-input":
        make_repo_scope_input(args)
    elif args.command == "make-diff-rank-input":
        make_diff_rank_input(args)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
