# codex-security runtime (vendored)

Vendored from [openai/codex-security](https://github.com/openai/codex-security),
plugin version `0.1.15`, commit `0facad0`.
Licensed Apache-2.0 (see LICENSE).

Source path: `sdk/typescript/_bundled_plugin/{scripts,schemas,references,preflight,examples}`

Installed and verified by `~/.claude/skills/cxsec-security/scripts/install.sh`.
Re-run it with `--check` to re-verify, `--force` to re-vendor.

This is the offline, model-agnostic half of the upstream plugin: stdlib-only Python
that validates scan-contract artifacts and deterministically generates `report.md`
and SARIF 2.1.0. It makes no network calls and needs no OpenAI credentials.

The upstream MCP server (`mcp/server.mjs`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out are deliberately NOT vendored.

Layout is load-bearing: `finalize_scan_contract.py` resolves schemas as
`<script_parent>/../schemas`, so `scripts/` and `schemas/` must stay siblings.

## Local modifications

The vendored code is **not** a pristine copy. See `patches/README.md`.

- `patches/0001-rebrand-sarif-output.patch` — renames the five cosmetic SARIF
  branding sites in `scripts/finalize_scan_contract.py` (`tool.driver.name`, the
  `partialFingerprints` namespace, and three `run.properties` keys) so generated
  SARIF is attributed to `cxsec-security`.

Re-vendoring overwrites this. Re-apply the patch and run the verification in
`patches/README.md` afterwards.

Canonical wire literals (`codex-security.*` documentTypes, the
`codex-security/v1` fingerprint algorithm, the `codex-security-snapshot/v1`
digest prefix) are intentionally unchanged — they are stamped by the finalizer,
never authored, and `mode-triage` relies on them to ingest genuine upstream
artifacts.
