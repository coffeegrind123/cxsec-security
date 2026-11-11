#!/usr/bin/env python3
"""Validate a sealed scan and list or select findings for tracking."""

# Upstream deleted validate_tracking_source.py in 0.9.0 (d408c1e4a, "share sealed
# scan reads with tracking") and moved it into its TypeScript MCP launcher
# (`--helper validate-tracking-source`, mcp-app/src/helpers/validate-tracking-source.ts
# over the "tracking" profile of sealed-contract.ts), which this port does not vendor.
# That profile reproduces the vendored Python reader, so this carried copy keeps
# delegating the whole bundle check to the vendored validate_scan_contract.py: every
# sealed digest, the schemas, derived identities, the generated report.md, and for
# current manifests the coverage view derived from scan.review. Brought in line with
# the TypeScript helper: the scan directory is home-expanded and canonicalised (a
# symlinked scan directory or ancestor alias is accepted), selectors stay mutually
# exclusive, and every failure is a one-line diagnostic with exit status 2.
# The CLI is unchanged.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Keep sibling helpers importable when Python starts in isolated mode.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_scan_contract as SCAN_CONTRACT

validate_contract = SCAN_CONTRACT.validate_contract
PREFLIGHT_FAILED = "tracking source preflight failed"


def _select_findings(
    findings: list[dict[str, Any]],
    finding_id: str | None,
    fingerprint: str | None,
) -> list[dict[str, Any]]:
    if finding_id is not None:
        matches = [finding for finding in findings if finding["findingId"] == finding_id]
    elif fingerprint is not None:
        matches = [
            finding for finding in findings if finding["fingerprints"]["primary"] == fingerprint
        ]
    else:
        return findings

    if len(matches) != 1:
        raise ValueError("the selector did not resolve exactly one finding")
    return matches


def validate_source(
    scan_dir: Path,
    *,
    finding_id: str | None = None,
    fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    if finding_id is not None and fingerprint is not None:
        raise ValueError("use only one of --finding-id or --fingerprint")

    canonical = Path(scan_dir).expanduser().resolve(strict=True)
    validated = validate_contract(canonical)
    return _select_findings(validated["findings"]["findings"], finding_id, fingerprint)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan_dir", help="Sealed scan directory.")
    parser.add_argument("--finding-id", metavar="ID")
    parser.add_argument("--fingerprint", metavar="FINGERPRINT")
    return parser.parse_args(argv)


def _escape_controls(text: str) -> str:
    return "".join(
        f"\\u{ord(character):04x}"
        if ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F
        else character
        for character in text
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        findings = validate_source(
            Path(args.scan_dir),
            finding_id=args.finding_id,
            fingerprint=args.fingerprint,
        )
    except (OSError, ValueError, KeyError, TypeError, RecursionError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            detail = str(exc.code)
        elif isinstance(exc, OSError) and exc.filename is not None:
            # str(OSError) quotes the path with repr(); print the path itself, escaped.
            detail = f"[Errno {exc.errno}] {exc.strerror}: {os.fsdecode(exc.filename)}"
        else:
            detail = str(exc)
        print(f"{PREFLIGHT_FAILED}: {_escape_controls(detail)}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding["findingId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
