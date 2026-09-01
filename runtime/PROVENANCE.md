# codex-security runtime (vendored)

Vendored from [openai/codex-security](https://github.com/openai/codex-security),
plugin version `0.1.24`, commit `d4b7d29`.
Full commit: `d4b7d29a87cb86c9072f7905ba867d02385d8fd3`
Licensed Apache-2.0 (see LICENSE).

Source path: `plugins/codex-security/{scripts,schemas,references,preflight,examples}`
plus `plugins/codex-security/skills/assess-patch-risk/scripts`, kept at its upstream depth.
(Upstream relocated the plugin from `sdk/typescript/_bundled_plugin` at 0.1.16+.)

Installed and verified by `~/.claude/skills/cxsec-security/scripts/install.sh`.
Re-run it with `--check` to re-verify, `--force` to re-vendor.

This is the offline, model-agnostic half of the upstream plugin: stdlib-only Python
that validates scan-contract artifacts and deterministically generates `report.md`
and SARIF 2.1.0. It makes no network calls and needs no OpenAI credentials.

The upstream MCP server (`mcp-app/`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out are deliberately NOT vendored.

Two paths are load-bearing. `finalize_scan_contract.py` resolves schemas as
`<script_parent>/../schemas`, so `scripts/` and `schemas/` must stay siblings.
`validate_patch_risk_assessment.py` resolves the plugin root as `parents[3]`, so it
must stay at `skills/assess-patch-risk/scripts/` directly under this root.

Needs Python 3.11+: `config_preflight.py` and `deep_scan_config.py` import stdlib
`tomllib`, falling back to third-party `tomli` on 3.9/3.10 when it is installed.

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
