"""Carried validate_tracking_source.py, held to upstream's current TypeScript contract.

Ported from openai/codex-security 0.9.1 sdk/typescript/tests-ts/tracking-source.test.ts
(and the 0.6.0 Python suite it replaced). Omitted: the Windows UTF-16 scan-root case,
the copied-launcher case (no launcher here), and the SDK-profile comparisons, which
exercise upstream's separate TypeScript reader. Run with: python3 -m pytest tests/
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PREFLIGHT = "tracking source preflight failed:"


class Fixture:
    def __init__(self, root: Path, scan_dir: Path, script: Path) -> None:
        self.root = root
        self.scan_dir = scan_dir
        self.script = script

    def read(self, name: str):
        return json.loads((self.scan_dir / name).read_text(encoding="utf-8"))

    def write(self, name: str, document) -> None:
        (self.scan_dir / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        manifest = self.read("scan-manifest.json")
        for artifact in manifest["scan"]["artifacts"]:
            if artifact["path"] == name:
                artifact["sha256"] = hashlib.sha256((self.scan_dir / name).read_bytes()).hexdigest()
        (self.scan_dir / "scan-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def run(self, *args: str, scan_dir: str | Path | None = None, env: dict | None = None):
        return subprocess.run(
            [sys.executable, "-I", str(self.script), str(scan_dir or self.scan_dir), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )


def make_fixture(tmp_path: Path, plugin_root: Path, example: str) -> Fixture:
    scan_dir = tmp_path / "sealed scan"
    shutil.copytree(plugin_root / "examples" / example, scan_dir)
    if os.name != "nt":
        scan_dir.chmod(0o700)
    return Fixture(tmp_path, scan_dir, plugin_root / "scripts" / "validate_tracking_source.py")


@pytest.fixture
def legacy(tmp_path: Path, plugin_root: Path) -> Fixture:
    return make_fixture(tmp_path, plugin_root, "legacy-completed-scan")


@pytest.fixture
def current(tmp_path: Path, plugin_root: Path) -> Fixture:
    return make_fixture(tmp_path, plugin_root, "completed-scan")


def ids(f: Fixture) -> list[str]:
    return [finding["findingId"] for finding in f.read("findings.json")["findings"]]


def test_tracks_a_current_scan_without_coverage_json(current: Fixture) -> None:
    assert not (current.scan_dir / "coverage.json").exists()
    result = current.run()
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(f"{finding_id}\n" for finding_id in ids(current))
    assert result.stderr == ""


def test_tracks_a_legacy_scan_with_coverage_json(legacy: Fixture) -> None:
    result = legacy.run()
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(f"{finding_id}\n" for finding_id in ids(legacy))


@pytest.mark.parametrize("selector", ["--finding-id", "--fingerprint"])
def test_selects_exactly_one_finding(legacy: Fixture, selector: str) -> None:
    finding = legacy.read("findings.json")["findings"][0]
    value = finding["findingId"] if selector == "--finding-id" else finding["fingerprints"]["primary"]
    result = legacy.run(selector, value)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{finding['findingId']}\n"

    missing = legacy.run(selector, "missing")
    assert missing.returncode == 2
    assert missing.stdout == ""
    assert missing.stderr.startswith(PREFLIGHT)
    assert "the selector did not resolve exactly one finding" in missing.stderr


def test_rejects_simultaneous_selectors(legacy: Fixture) -> None:
    finding = legacy.read("findings.json")["findings"][0]
    result = legacy.run(
        "--finding-id", finding["findingId"], "--fingerprint", finding["fingerprints"]["primary"]
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith(PREFLIGHT)
    assert "use only one of --finding-id or --fingerprint" in result.stderr


def test_prints_help_successfully(legacy: Fixture) -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(legacy.script), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert "--finding-id" in result.stdout and "--fingerprint" in result.stdout


def test_escapes_controls_in_a_missing_scan_path(legacy: Fixture) -> None:
    result = legacy.run(scan_dir=legacy.root / "missing\x1b[31mscan")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith(PREFLIGHT)
    assert "\x1b" not in result.stderr
    assert "\\u001b" in result.stderr
    assert "Traceback" not in result.stderr


def test_expands_a_home_relative_scan_directory(legacy: Fixture) -> None:
    env = {**os.environ, "HOME": str(legacy.root)}
    result = legacy.run(scan_dir=f"~/{legacy.scan_dir.name}", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{ids(legacy)[0]}\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks")
def test_canonicalizes_a_scan_directory_symlink(legacy: Fixture) -> None:
    alias = legacy.root / "scan alias"
    alias.symlink_to(legacy.scan_dir, target_is_directory=True)
    result = legacy.run(scan_dir=alias)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{ids(legacy)[0]}\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks")
def test_accepts_a_scan_beneath_an_ancestor_alias(legacy: Fixture, tmp_path_factory) -> None:
    alias = tmp_path_factory.mktemp("alias") / "parent alias"
    alias.symlink_to(legacy.root, target_is_directory=True)
    result = legacy.run(scan_dir=alias / legacy.scan_dir.name)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{ids(legacy)[0]}\n"


def test_requires_the_generated_report(legacy: Fixture) -> None:
    (legacy.scan_dir / "report.md").unlink()
    result = legacy.run()
    assert result.returncode == 2
    assert result.stdout == ""
    assert "report.md" in result.stderr


@pytest.mark.parametrize("name", ["findings.json", "coverage.json"])
def test_rejects_changed_bytes_in_a_sealed_artifact(legacy: Fixture, name: str) -> None:
    with (legacy.scan_dir / name).open("a", encoding="utf-8") as handle:
        handle.write("\n")
    result = legacy.run()
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith(PREFLIGHT)
    assert "Traceback" not in result.stderr


def test_rejects_duplicate_findings_before_selecting(legacy: Fixture) -> None:
    findings = legacy.read("findings.json")
    findings["findings"].append(json.loads(json.dumps(findings["findings"][0])))
    legacy.write("findings.json", findings)
    result = legacy.run("--finding-id", findings["findings"][0]["findingId"])
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith(PREFLIGHT)


def test_validates_an_unselected_finding_against_the_schema(legacy: Fixture) -> None:
    findings = legacy.read("findings.json")
    findings["findings"][0]["severity"]["level"] = "unsupported"
    legacy.write("findings.json", findings)
    result = legacy.run("--fingerprint", "anything")
    assert result.returncode == 2
    assert result.stderr.startswith(PREFLIGHT)
    assert "the selector did not resolve" not in result.stderr


def test_validates_a_finding_identity(legacy: Fixture) -> None:
    findings = legacy.read("findings.json")
    findings["findings"][0]["findingId"] = "csf_" + "0" * 24
    legacy.write("findings.json", findings)
    result = legacy.run()
    assert result.returncode == 2
    assert result.stderr.startswith(PREFLIGHT)


def test_rejects_a_report_only_directory(tmp_path: Path, plugin_root: Path) -> None:
    scan_dir = tmp_path / "report only"
    scan_dir.mkdir()
    (scan_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    script = plugin_root / "scripts" / "validate_tracking_source.py"
    result = subprocess.run(
        [sys.executable, "-I", str(script), str(scan_dir)], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith(PREFLIGHT)
    assert "Traceback" not in result.stderr
