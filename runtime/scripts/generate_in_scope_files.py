#!/usr/bin/env python3
"""Generate the shared, deterministically ordered security-scan file inventory."""

# Upstream deleted generate_in_scope_files.py in 0.7.0 (05cceee24, "run inventory and
# ranking helpers in Node") and moved it into its TypeScript MCP launcher
# (`launch_codex_security_mcp --helper generate-in-scope-files`, implemented in
# mcp-app/src/helpers/generate-inventory.ts, inventory-git.ts and inventory-paths.ts),
# which this port does not vendor. This carried copy is the last upstream Python
# version brought in line with that implementation:
#   - Git runs through the vendored workbench_target.git_command: a trusted executable
#     outside the scanned repository (or CODEX_SECURITY_GIT), inherited GIT_DIR-style
#     selection cleared, literal pathspecs, no fsmonitor hook, no lazy fetches.
#   - An empty .git directory (a sandbox placeholder) does not make a worktree.
#   - A Git listing failure is reported instead of silently dropping ignored tracked
#     files; an unavailable Git still falls back to ripgrep alone.
#   - Diff inventories share the committed-blob and working-file sampler with
#     generate_rank_input.py, so both classify binary content over every byte.
#   - Inventories are replaced atomically through an exclusive 0600 temporary file.
# The CLI is unchanged.

from __future__ import annotations

import argparse
import os
import secrets
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# Some plugin hosts launch Python with safe-path isolation enabled.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rank_preview import SourceSampler, sample_file
from workbench_target import SOURCE_METADATA_DIRECTORIES, git_changed_paths, git_command

GIT_UNAVAILABLE = 127


class InventoryError(ValueError):
    """Raised when the repository, scope, or inventory cannot be used safely."""


def windows_stream_component(path: Path) -> str | None:
    """Return the first NTFS alternate-data-stream component."""
    if os.name != "nt":
        return None
    return next(
        (component for component in path.parts if component != path.anchor and ":" in component),
        None,
    )


def escape_controls(text: str) -> str:
    return "".join(
        f"\\u{ord(character):04x}"
        if ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F or character in "  "
        else character
        for character in text
    )


def regular(path: Path) -> bool:
    """A non-symlink regular file. Missing or unreachable paths are not regular."""
    try:
        return not path.is_symlink() and path.is_file()
    except OSError:
        return False


def contained(repository: Path, path: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(repository)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def in_worktree(repository: Path) -> bool:
    """A .git file, or a .git directory that is more than an empty placeholder."""
    for ancestor in (repository, *repository.parents):
        marker = ancestor / ".git"
        if not os.path.lexists(marker):
            continue
        if not marker.is_dir() or os.path.lexists(marker / "HEAD") or (marker / "index").is_file():
            return True
    return False


def resolve_repository(value: str) -> Path:
    """Resolve the repository once so every scope is bound to its real root."""
    try:
        repository = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InventoryError(f"Repo path not found: {value}") from error
    if not repository.is_dir():
        raise InventoryError(f"Repo path not found: {repository}")
    return repository


def resolve_scope(repository: Path, value: str) -> str:
    """Preserve ripgrep's relative path spelling while rejecting escaped scopes."""
    if not value or "\0" in value:
        raise InventoryError("--scope: expected a non-empty file or directory")

    requested = Path(value).expanduser()
    stream = windows_stream_component(requested)
    if stream is not None:
        raise InventoryError(f"--scope: NTFS alternate data streams are not supported: {stream}")
    scope = requested if requested.is_absolute() else repository / requested
    try:
        resolved = scope.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise InventoryError(f"--scope: path does not exist: {value}") from error

    try:
        relative = resolved.relative_to(repository)
    except ValueError as error:
        raise InventoryError(f"--scope: path must remain inside --repo: {value}") from error

    if not resolved.is_dir() and not resolved.is_file():
        raise InventoryError(f"--scope: expected a file or directory: {value}")

    if requested.is_absolute():
        return relative.as_posix() if relative.parts else "."
    return value


def resolve_output(value: str) -> Path:
    """Reject direct symlink outputs without constraining the artifact root."""
    if not value or "\0" in value:
        raise InventoryError("--out: expected an inventory file path")
    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise InventoryError("--out: refusing to replace a symbolic link")
    try:
        output = requested.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as error:
        raise InventoryError(f"--out: cannot resolve inventory path: {value}") from error
    if output.exists() and not output.is_file():
        raise InventoryError(f"--out: expected a regular file path: {output}")
    return output


def tool_status(returncode: int) -> str:
    if returncode < 0:
        try:
            return f"terminated by {signal.Signals(-returncode).name}"
        except ValueError:
            return f"terminated by signal {-returncode}"
    return f"exited with status {returncode}"


def ignored_tracked_paths(repository: Path, scope: str) -> list[bytes]:
    """Tracked files that ignore rules would hide from ripgrep. Empty without Git."""
    result = git_command(
        repository,
        "ls-files",
        "--cached",
        "--ignored",
        "--exclude-standard",
        "-z",
        "--",
        scope,
        text=False,
        offline=True,
    )
    if result.returncode == GIT_UNAVAILABLE and not result.stderr:
        return []
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise InventoryError(f"git ls-files: {detail or 'Git ' + tool_status(result.returncode)}")
    return [path for path in result.stdout.split(b"\0") if path]


def generate_in_scope_files(repository: Path, scope: str, output: Path) -> int:
    """Atomically write the exact ripgrep inventory sorted as ``LC_ALL=C``."""
    command = [
        "rg",
        "--files",
        "--null",
        "--hidden",
        "--path-separator",
        "/",
        # Prune metadata and its contents even when the scope starts inside it.
        "--glob",
        "!**/{.git,.svn}",
        "--glob",
        "!**/{.git,.svn}/**",
        "--",
        scope,
    ]
    with tempfile.TemporaryFile(mode="w+b") as inventory:
        try:
            result = subprocess.run(
                command,
                cwd=repository,
                stdout=inventory,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as error:
            raise InventoryError(f"could not run ripgrep: {error}") from error

        if result.returncode not in (0, 1):
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            message = f"ripgrep {tool_status(result.returncode)}"
            raise InventoryError(f"{message}: {detail}" if detail else message)

        if in_worktree(repository):
            prefix = b"./" if scope == "." or scope.startswith("./") else b""
            for path in ignored_tracked_paths(repository, scope):
                if regular(repository / os.fsdecode(path)):
                    inventory.write(prefix + path + b"\0")

        inventory.seek(0)
        rows: list[bytes] = []
        for path in inventory.read().split(b"\0"):
            if not path or not SOURCE_METADATA_DIRECTORIES.isdisjoint(os.fsdecode(path).split("/")):
                continue
            if b"\n" in path or b"\r" in path:
                raise InventoryError(
                    "Repository contains a path that cannot fit in the file inventory"
                )
            rows.append(path + b"\n")

    return write_inventory(output, sorted(set(rows)))


def git_failure(error: subprocess.CalledProcessError) -> str:
    """Describe a failed Git diff or listing the way the upstream helper does."""
    stderr = error.stderr or b""
    detail = (stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr).strip()
    command = [os.fsdecode(part) for part in (error.cmd or [])]
    if detail and "diff" in command:
        status = tool_status(error.returncode).replace("exited with status", "exit code")
        status = status.replace("terminated by ", "")
        return f"Git diff failed with {status}: {escape_controls(detail)}"
    return detail or f"Git {tool_status(error.returncode)}"


def changed_paths(repository: Path, base: str, head: str, mode: str) -> list[tuple[str, str]]:
    """Changed regular files as (repository-relative POSIX name, status)."""
    try:
        changes = git_changed_paths(repository, base, head, mode)
    except subprocess.CalledProcessError as error:
        raise InventoryError(git_failure(error)) from error
    return [(path.relative_to(repository).as_posix(), status) for path, status in changes]


def blob_samples(repository: Path, names: list[str]) -> list[tuple[bytes, bool] | None]:
    """Sample each committed blob in one cat-file batch, streaming the bodies.

    Each entry is (preview window, binary) or None when the object is missing or the
    batch failed. NUL-terminated input is used only when a name needs it, so Git
    versions without ``cat-file --batch -z`` still serve ordinary names.
    """
    if not names:
        return []
    nul_input = any("\n" in name or "\r" in name for name in names)
    separator = "\0" if nul_input else "\n"
    request = os.fsencode(separator.join(names) + separator)
    with tempfile.TemporaryFile(mode="w+b") as sink:
        result = git_command(
            repository,
            "cat-file",
            "--batch",
            *(["-z"] if nul_input else []),
            text=False,
            input_data=request,
            stdout_file=sink,
            offline=True,
        )
        if result.returncode != 0:
            return [None] * len(names)
        sink.seek(0)
        try:
            samples = _read_batch(sink, names)
        except ValueError:
            return [None] * len(names)
    return samples


def _read_batch(output, names: list[str]) -> list[tuple[bytes, bool] | None]:
    samples: list[tuple[bytes, bool] | None] = []
    for name in names:
        header = output.readline()
        raw = os.fsencode(name)
        # Missing lookups echo the whole request, including embedded newlines.
        if header and raw.startswith(header):
            header += output.read(len(raw) - len(header)) + output.readline()
        if header in (raw + b" missing\n", raw + b" ambiguous\n"):
            samples.append(None)
            continue
        fields = header.split(b" ")
        if len(fields) != 3 or not header.endswith(b"\n"):
            raise ValueError("invalid batch header")
        size = int(fields[2])
        if size < 0:
            raise ValueError("invalid blob size")
        sampler = SourceSampler()
        remaining = size
        while remaining:
            chunk = output.read(min(remaining, 64 * 1024))
            if not chunk:
                raise ValueError("truncated blob")
            sampler.consume(chunk)
            remaining -= len(chunk)
        if output.read(1) != b"\n":
            raise ValueError("Invalid Git blob framing")
        samples.append(sampler.finish() if fields[1] == b"blob" else None)
    if output.read(1):
        raise ValueError("unexpected batch output")
    return samples


def diff_samples(
    repository: Path, base: str, head: str, mode: str, changes: list[tuple[str, str]]
) -> dict[str, tuple[bytes, bool]]:
    """Read the committed side of every change that is not a local working file."""
    refs = [
        (name, f"{base if status == 'D' else head}:{name}")
        for name, status in changes
        if mode == "revisions" or status == "D"
    ]
    samples: dict[str, tuple[bytes, bool]] = {}
    for (name, ref), sample in zip(refs, blob_samples(repository, [ref for _, ref in refs])):
        if sample is None:
            raise InventoryError(f"Unable to read committed diff blob: {ref}")
        samples[name] = sample
    return samples


def generate_diff_in_scope_files(
    repository: Path,
    base: str,
    head: str,
    mode: str,
    output: Path,
) -> int:
    """Reuse the diff selection without generating previews or duplicate worklists."""
    try:
        changes = changed_paths(repository, base, head, mode)
    except InventoryError as error:
        raise InventoryError(f"could not resolve the selected Git changes: {error}") from error
    samples = diff_samples(repository, base, head, mode, changes)

    rows: list[bytes] = []
    for name, _status in changes:
        if name in samples:
            if samples[name][1]:
                continue
        else:
            path = repository / name
            if not regular(path) or not contained(repository, path) or sample_file(path)[1]:
                continue
        if "\n" in name or "\r" in name:
            raise InventoryError("Git changes contain a path that cannot fit in the file inventory")
        rows.append(os.fsencode(name) + b"\n")

    return write_inventory(output, sorted(set(rows)))


def write_inventory(output: Path, rows: list[bytes]) -> int:
    """Replace a complete inventory atomically, keeping failures from corrupting the old one."""
    output.parent.mkdir(parents=True, exist_ok=True)
    # Including the output name can exceed the filesystem's 255-byte name limit.
    temporary = output.parent / f".{secrets.token_hex(12)}.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.writelines(rows)
        temporary.replace(output)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Repository root.")
    parser.add_argument("--scope", required=True, help="File or directory within the repository.")
    parser.add_argument("--out", required=True, help="Destination for the file inventory.")
    parser.add_argument("--diff-base", help="Authoritative Git base for a changed-file inventory.")
    parser.add_argument("--diff-head", default="HEAD", help="Authoritative Git head revision.")
    parser.add_argument(
        "--diff-mode",
        choices=("revisions", "local-patch"),
        default="revisions",
        help="Use committed revisions or the current staged and unstaged patch.",
    )
    args = parser.parse_args()

    try:
        repository = resolve_repository(args.repo)
        output = resolve_output(args.out)
        scope = resolve_scope(repository, args.scope)
        if args.diff_base is None:
            count = generate_in_scope_files(repository, scope, output)
        elif scope not in (".", "./"):
            raise InventoryError("--scope: diff scans must use the repository root")
        else:
            count = generate_diff_in_scope_files(
                repository,
                args.diff_base,
                args.diff_head,
                args.diff_mode,
                output,
            )
    except (OSError, ValueError, SystemExit) as error:
        message = error.code if isinstance(error, SystemExit) else error
        print(f"generate_in_scope_files: {message}", file=sys.stderr)
        raise SystemExit(2) from error

    print(f"Recorded {count} in-scope files.")


if __name__ == "__main__":
    main()
