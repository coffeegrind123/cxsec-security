"""Inventory and worklist behaviour upstream added after 0.6.0, held for the carried helpers.

Ported from openai/codex-security 0.9.1 sdk/typescript/tests-ts/inventory-input.test.ts
and diff-rank-input.test.ts: the cases that changed behaviour since the 0.6.0 Python
suites (test_generate_in_scope_files.py, test_generate_rank_input.py) were written.
Omitted: Windows-only cases (UTF-16 names, junctions, drive roots, raw tool lookup), the
bundled-ripgrep and raw-argv shell-launch cases specific to the Node launcher, and
macOS case-folding cases. Run with: python3 -m pytest tests/
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

POSIX = os.name != "nt"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


def run(script: Path, *args: str, env: dict | None = None, cwd: Path | None = None):
    return subprocess.run(
        [sys.executable, "-I", str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        check=False,
    )


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def inventory(plugin_scripts: Path) -> Path:
    return plugin_scripts / "generate_in_scope_files.py"


@pytest.fixture
def rank(plugin_scripts: Path) -> Path:
    return plugin_scripts / "generate_rank_input.py"


def test_inventory_helpers_print_usage_without_a_repository(inventory: Path, rank: Path) -> None:
    for args in ((inventory, "--help"), (rank, "make-repo-scope-input", "--help"), (rank, "make-diff-rank-input", "--help")):
        result = run(*args)
        assert result.returncode == 0, result.stderr
        assert "--repo" in result.stdout and "--out" in result.stdout


@pytest.mark.parametrize("command", ["make-repo-rank-input", "select-deep-review-input", "make-rank-shards"])
def test_retired_ranking_helpers_stay_unavailable(rank: Path, command: str) -> None:
    result = run(rank, command, "--help")
    assert result.returncode == 2


def test_empty_git_directory_placeholder_is_not_a_worktree(tmp_path: Path, inventory: Path) -> None:
    repo = tmp_path / "sandbox"
    (repo / ".git").mkdir(parents=True)
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (repo / "ignored.py").write_text("print(2)\n", encoding="utf-8")
    output = tmp_path / "in_scope_files.txt"
    result = run(inventory, "--repo", str(repo), "--scope", ".", "--out", str(output))
    assert result.returncode == 0, result.stderr
    # ripgrep alone decides; no git ls-files failure for the placeholder.
    assert b"./app.py\n" in output.read_bytes()
    assert b"ignored.py" not in output.read_bytes()


@pytest.mark.skipif(not POSIX, reason="POSIX executables")
def test_git_listing_failure_is_reported_not_dropped(tmp_path: Path, inventory: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    fake = tools / "git"
    fake.write_text("#!/bin/sh\necho 'fatal: synthetic listing failure' >&2\nexit 128\n", encoding="utf-8")
    fake.chmod(0o755)
    output = tmp_path / "in_scope_files.txt"
    output.write_bytes(b"previous\n")
    env = {**os.environ, "CODEX_SECURITY_GIT": str(fake)}
    result = run(inventory, "--repo", str(repo), "--scope", ".", "--out", str(output), env=env)
    assert result.returncode == 2
    assert "git ls-files: fatal: synthetic listing failure" in result.stderr
    assert output.read_bytes() == b"previous\n"


@pytest.mark.skipif(not POSIX, reason="POSIX executables")
def test_git_inside_the_scanned_repository_is_never_run(tmp_path: Path, rank: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "initial")
    (repo / "app.py").write_text("print(2)\n", encoding="utf-8")
    planted = repo / "bin"
    planted.mkdir()
    marker = tmp_path / "planted-git-ran"
    (planted / "git").write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n", encoding="utf-8")
    (planted / "git").chmod(0o755)
    output = tmp_path / "rank_input.jsonl"
    env = {k: v for k, v in os.environ.items() if k != "CODEX_SECURITY_GIT"}
    env["PATH"] = f"{planted}{os.pathsep}{env.get('PATH', '')}"
    result = run(
        rank, "make-diff-rank-input", "--repo", str(repo), "--base", "HEAD",
        "--mode", "local-patch", "--out", str(output), env=env,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert "app.py" in [row["path"] for row in rows(output)]


def test_inventory_clears_inherited_repository_selection(tmp_path: Path, rank: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / ".gitignore").write_text("tracked.py\n", encoding="utf-8")
    (repo / "tracked.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "--force", "tracked.py")
    scopes = tmp_path / "scopes.json"
    scopes.write_text('["."]', encoding="utf-8")
    output = tmp_path / "scoped.jsonl"
    env = {**os.environ, "GIT_DIR": str(tmp_path / "missing-git"), "GIT_WORK_TREE": str(tmp_path)}
    result = run(
        rank, "make-repo-scope-input", "--repo", str(repo), "--scopes-file", str(scopes),
        "--out", str(output), env=env,
    )
    assert result.returncode == 0, result.stderr
    assert [row["path"] for row in rows(output)] == [".gitignore", "tracked.py"]


@pytest.mark.skipif(not POSIX, reason="POSIX symlinks")
def test_local_diff_reviews_a_file_replaced_by_a_directory_as_deleted(tmp_path: Path, rank: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "kept.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "replaced.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "initial")
    (repo / "kept.py").write_text("print(2)\n", encoding="utf-8")
    (repo / "replaced.py").unlink()
    (repo / "replaced.py").mkdir()
    output = tmp_path / "rank_input.jsonl"
    result = run(
        rank, "make-diff-rank-input", "--repo", str(repo), "--base", "HEAD",
        "--mode", "local-patch", "--out", str(output),
    )
    assert result.returncode == 0, result.stderr
    by_path = {row["path"]: row for row in rows(output)}
    assert by_path["kept.py"]["preview"] == "print(2)"
    # The directory is not a reviewable working file: the path is reviewed as a
    # deletion from its committed side, which carries no preview.
    assert by_path["replaced.py"]["preview"] == ""


@pytest.mark.parametrize("value", ["1_000", "1.5", "abc", ""])
def test_preview_bytes_must_be_a_plain_integer(tmp_path: Path, rank: Path, value: str) -> None:
    repo = make_repo(tmp_path)
    result = run(
        rank, "make-diff-rank-input", "--repo", str(repo), "--base", "HEAD",
        "--out", str(tmp_path / "out.jsonl"), f"--preview-bytes={value}",
    )
    assert result.returncode == 2
    assert "--preview-bytes must be an integer" in result.stderr


@pytest.mark.parametrize("value", ["-5", "0", " 7 ", "+3"])
def test_preview_bytes_accepts_signed_integers(tmp_path: Path, rank: Path, value: str) -> None:
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("print('hello world')\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "initial")
    (repo / "app.py").write_text("print('changed text')\n", encoding="utf-8")
    output = tmp_path / "out.jsonl"
    result = run(
        rank, "make-diff-rank-input", "--repo", str(repo), "--base", "HEAD",
        "--mode", "local-patch", "--out", str(output), "--preview-bytes", value,
    )
    assert result.returncode == 0, result.stderr
    preview = rows(output)[0]["preview"]
    budget = int(value.strip())
    assert preview == "" if budget <= 0 else len(preview.encode()) <= budget


def test_scope_rows_sort_by_code_point_and_escape_separators(tmp_path: Path, rank: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    names = ["b.py", "a line.py", "é.py", "Z.py", "\U0001f600.py", "Ａ.py"]
    for name in names:
        (repo / name).write_text("x\n", encoding="utf-8")
    scopes = tmp_path / "scopes.json"
    scopes.write_text(json.dumps(names), encoding="utf-8")
    output = tmp_path / "scoped.jsonl"
    result = run(
        rank, "make-repo-scope-input", "--repo", str(repo), "--scopes-file", str(scopes),
        "--out", str(output),
    )
    assert result.returncode == 0, result.stderr
    raw = output.read_bytes()
    assert raw.isascii()
    assert b"\\u2028" in raw
    assert [row["path"] for row in rows(output)] == sorted(names)


def test_explicit_scopes_are_literal_and_not_home_expanded(tmp_path: Path, rank: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "~").mkdir(parents=True)
    (repo / "~" / "file.py").write_text("x\n", encoding="utf-8")
    (repo / "glob[1].py").write_text("x\n", encoding="utf-8")
    scopes = tmp_path / "scopes.json"
    scopes.write_text(json.dumps(["~", "glob[1].py", "./~/./file.py"]), encoding="utf-8")
    output = tmp_path / "scoped.jsonl"
    env = {**os.environ, "HOME": str(tmp_path / "elsewhere")}
    result = run(
        rank, "make-repo-scope-input", "--repo", str(repo), "--scopes-file", str(scopes),
        "--out", str(output), env=env,
    )
    assert result.returncode == 0, result.stderr
    assert [row["path"] for row in rows(output)] == ["glob[1].py", "~/file.py"]


@pytest.mark.skipif(not POSIX, reason="POSIX symlinks")
def test_scope_rejects_a_link_before_lexical_parent_traversal(tmp_path: Path, rank: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "real").mkdir(parents=True)
    (repo / "real" / "file.py").write_text("x\n", encoding="utf-8")
    outside = tmp_path / "outside"
    (outside / "nested").mkdir(parents=True)
    (repo / "link").symlink_to(outside / "nested", target_is_directory=True)
    scopes = tmp_path / "scopes.json"
    scopes.write_text(json.dumps(["link/../real"]), encoding="utf-8")
    result = run(
        rank, "make-repo-scope-input", "--repo", str(repo), "--scopes-file", str(scopes),
        "--out", str(tmp_path / "scoped.jsonl"),
    )
    assert result.returncode != 0
    assert "must not contain symbolic links" in result.stderr


def test_diff_inventory_expands_a_home_relative_repository(tmp_path: Path, inventory: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "initial")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text("print(2)\n", encoding="utf-8")
    output = tmp_path / "in_scope_files.txt"
    env = {**os.environ, "HOME": str(tmp_path)}
    result = run(
        inventory, "--repo", "~/repo", "--scope", ".", "--out", str(output),
        "--diff-base", base, "--diff-mode", "local-patch", env=env,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == b"app.py\n"


def test_failed_inventory_preserves_the_existing_file_and_leaves_no_temporary(
    tmp_path: Path, inventory: Path
) -> None:
    repo = make_repo(tmp_path)
    output = tmp_path / "out" / "in_scope_files.txt"
    output.parent.mkdir()
    output.write_bytes(b"previous\n")
    result = run(
        inventory, "--repo", str(repo), "--scope", ".", "--out", str(output),
        "--diff-base", "no-such-revision",
    )
    assert result.returncode == 2
    assert "could not resolve the selected Git changes" in result.stderr
    assert output.read_bytes() == b"previous\n"
    assert sorted(path.name for path in output.parent.iterdir()) == ["in_scope_files.txt"]


def test_unreadable_committed_blob_is_named(tmp_path: Path, rank: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "one")
    (repo / "app.py").write_text("print(2)\n", encoding="utf-8")
    git(repo, "commit", "-qam", "two")
    blob = git(repo, "rev-parse", "HEAD:app.py")
    obj = repo / ".git" / "objects" / blob[:2] / blob[2:]
    obj.chmod(0o644)
    obj.unlink()
    result = run(
        rank, "make-diff-rank-input", "--repo", str(repo), "--base", "HEAD~1",
        "--out", str(tmp_path / "out.jsonl"),
    )
    assert result.returncode == 1
    assert "Unable to read committed diff blob: HEAD:app.py" in result.stderr
