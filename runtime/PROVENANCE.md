# codex-security runtime (vendored)

Vendored from [openai/codex-security](https://github.com/openai/codex-security),
plugin version `0.1.32`, commit `7c19cce`.
Full commit: `7c19cce7224af29628cd10c218444d5c0e8fdd1c`
Licensed Apache-2.0 (see LICENSE).

Source path: `plugins/codex-security/{scripts,schemas,references,preflight,examples}`
plus `plugins/codex-security/skills/assess-patch-risk/scripts`, kept at its upstream depth.

Installed by `cxsec-security/scripts/install.sh` on 2026-10-03T10:33:38Z.

This is the offline, model-agnostic half of the upstream plugin: stdlib-only Python
that validates scan-contract artifacts and deterministically generates `report.md`
and SARIF 2.1.0. It makes no network calls and needs no OpenAI credentials.

The upstream MCP server (`mcp-app/`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out are deliberately NOT vendored.

Layout is load-bearing: `finalize_scan_contract.py` resolves schemas as
`<script_parent>/../schemas`, so `scripts/` and `schemas/` must stay siblings.

## Local modifications

The vendored code is **not** a pristine copy. See `patches/README.md`.

- `patches/0001-rebrand-sarif-output.patch` — renames the five cosmetic SARIF branding sites in
  `scripts/finalize_scan_contract.py` so generated SARIF is attributed to
  `cxsec-security`.
- `scripts/resolve_security_md.py` — a carried-forward local addition. Upstream
  ported the offline SECURITY.md policy resolver into the MCP app in 0.1.28
  (`launch_codex_security_mcp --helper resolve-security-md`) and deleted the
  standalone helper. This port does not vendor the MCP app, so it keeps the last
  upstream Python version (byte-identical 0.1.24–0.1.26), which mode 7 and the
  repo-scan policy chain invoke. Self-contained stdlib; same concatenation
  semantics the TS helper documents.

Re-vendoring overwrites both. `install.sh` re-applies the patch and restores the
local additions automatically, then verifies the result.

Canonical wire literals (`codex-security.*` documentTypes, the
`codex-security/v1` fingerprint algorithm, the `codex-security-snapshot/v1`
digest prefix) are intentionally unchanged — they are stamped by the finalizer,
never authored, and `mode-triage` relies on them to ingest genuine upstream
artifacts.
