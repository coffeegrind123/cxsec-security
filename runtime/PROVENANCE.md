# codex-security runtime (vendored)

Vendored from [openai/codex-security](https://github.com/openai/codex-security),
plugin version `0.9.1`, commit `fe1089a`.
Full commit: `fe1089ab514599931ff0ce77a82dc8c4a99201ea`
Licensed Apache-2.0 (see LICENSE).

Source path: `plugins/codex-security/{scripts,schemas,references,examples,shared,skills/threat-model-visualize/scripts,skills/threat-model-visualize/assets,skills/threat-model-visualize/references}`.

Installed by `cxsec-security/scripts/install.sh` on 2026-11-10T23:56:02Z.

This is the offline, model-agnostic half of the upstream plugin: stdlib-only Python
that validates scan-contract artifacts and deterministically generates `report.md`
and SARIF 2.1.0. It makes no network calls and needs no OpenAI credentials.

The upstream MCP server (`mcp-app/`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out are deliberately NOT vendored. The offline
explorer builder, assets and references of `skills/threat-model-visualize` are
vendored unchanged for mode 13.

Layout is load-bearing: `finalize_scan_contract.py` resolves schemas as
`<script_parent>/../schemas`, so `scripts/` and `schemas/` must stay siblings.

## Local modifications

The vendored code is **not** a pristine copy. See `patches/README.md`.

- `patches/0001-rebrand-sarif-output.patch` — renames the four cosmetic SARIF branding sites in
  `scripts/finalize_scan_contract.py` so generated SARIF is attributed to
  `cxsec-security`.
- `scripts/resolve_security_md.py` — a carried-forward local addition. Upstream
  ported the offline SECURITY.md policy resolver into the MCP app in 0.1.28
  (`launch_codex_security_mcp --helper resolve-security-md`) and deleted the
  standalone helper. This port does not vendor the MCP app, so it keeps the last
  upstream Python version (byte-identical 0.1.24–0.1.26), which mode 7 and the
  repo-scan policy chain invoke. Self-contained stdlib; same concatenation
  semantics the TS helper documents, and it tracks the current TS resolver (no
  1 MiB policy cap since 0.8.0).
- `scripts/normalize_candidates.py` — a carried-forward local addition. Upstream
  ported diff-scan candidate normalization into the MCP app in 0.2.0 and deleted
  the Python helper. Kept at its last upstream version with the later TypeScript
  behaviour changes ported back (raw POSIX path bytes, final-row and ambiguous
  carriage-return handling). Output and `candidate_id` values are unchanged.
- `skills/assess-patch-risk/scripts/validate_patch_risk_assessment.py` — a
  carried-forward local addition, kept at its upstream depth (it resolves the
  plugin root as `parents[3]`). Upstream ported it into the MCP app in 0.3.0;
  the carried copy includes the later rule rejecting `merge` with critical
  regression likelihood.
- `scripts/copy_deep_review_input.py`, `scripts/bind_repo_scopes.py` — carried-forward
  local additions. Upstream retired these `generate_rank_input.py` subcommands
  (`copy-deep-review-input`, `bind-repo-scopes`) into the MCP launcher in 0.3.0.
  Re-implemented from the TypeScript helpers; same CLI and output format.
  `bind_repo_scopes.py` binds into the manifest only, as the 0.9.x helper does.
- `scripts/generate_in_scope_files.py`, `scripts/generate_rank_input.py`
  (`make-repo-scope-input`, `make-diff-rank-input`), `scripts/rank_preview.py` —
  carried-forward local additions. Upstream moved inventory, ranking and preview
  generation into its MCP launcher in 0.7.0 and deleted the Python. Kept at their
  last upstream versions with the later TypeScript behaviour ported back (trusted,
  sanitised Git; whole-file binary sampling; empty-`.git` placeholders; reported Git
  listing failures). Same CLIs and output formats.
- `scripts/validate_tracking_source.py` — a carried-forward local addition. Upstream
  moved the tracking preflight into its MCP launcher in 0.9.0. It delegates to the
  vendored `validate_scan_contract.py`, which upstream's TypeScript tracking reader
  mirrors, and adds home expansion, scan-directory canonicalisation and escaped
  one-line diagnostics. Same CLI.

All carried helpers are held to upstream's current TypeScript test suites, ported to
pytest under the skill repo's `tests/`.

Re-vendoring overwrites the patch and removes the additions. `install.sh` re-applies the patch and restores the
local additions automatically, then verifies the result.

Canonical wire literals (`codex-security.*` documentTypes, the
`codex-security/v1` fingerprint algorithm, the `codex-security-snapshot/v1`
digest prefix) are intentionally unchanged — they are stamped by the finalizer,
never authored, and `mode-triage` relies on them to ingest genuine upstream
artifacts.
