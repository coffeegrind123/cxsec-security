# Scan Artifact Paths

Use these shared path conventions for security scan workflows unless the user explicitly provides different input or output paths.

## Base Paths

- `cxsec_home=$CXSEC_HOME` (vendored runtime root, default `~/.claude/codex-security`)
- `repo_name=<basename of repo_root>`
- `target_id=<stable scan target identity from scan-contract.md>`
- `system_temp_dir=<platform temporary directory>`
- `security_scans_dir=<system_temp_dir>/codex-security-scans/<repo_name>`
- `scan_id=<commit>_<scan timestamp>`
- `scan_dir=<security_scans_dir>/<scan_id>`
- `target_paths_file=<explicitly enumerated scoped-path file>` when the user supplies one. Treat it as read-only scope input: pass it directly to `make-repo-scope-input --scopes-file` and `bind-repo-scopes --scopes-file` before finalization, and do not print, evaluate, modify, or treat its contents as shell syntax.
- `artifacts_dir=<scan_dir>/artifacts`
- `context_dir=<artifacts_dir>/01_context`
- `discovery_dir=<artifacts_dir>/02_discovery`
- `coverage_dir=<artifacts_dir>/03_coverage`
- `reconciliation_dir=<artifacts_dir>/04_reconciliation`
- `findings_dir=<artifacts_dir>/05_findings`

The plugin resolves the platform temporary directory automatically. For a manual workflow, use the active process temporary directory (for example, `%TEMP%` on Windows or `$TMPDIR` when configured on Unix-like hosts) instead of hardcoding `/tmp`.

Resolve `<python_command>` to the configured Python interpreter (`"$PYTHON"` when one is provided), otherwise use `python3`.

## Threat Model (Phase 1) Paths

- Resolved SECURITY.md guidance: `<context_dir>/security_guidance.md`
- Repository-scoped threat model: `<security_scans_dir>/threat_model.md`
- Canonical per-scan model: `scan.threatModel` in `<scan_dir>/scan-manifest.json`, retained in `<scan_dir>/checkpoint-findings.json` as soon as architecture mapping produces it. Later phases use this retained canonical content.
- Human-readable per-scan model: `<scan_dir>/threatmodel.md`. `finalize_scan_contract.py` regenerates it from the canonical model at finalization; before then you may write the same text there as the working projection. It is never an independently authored input.
- When a repository-scoped threat model already exists, retain its exact text as the canonical model (`{ "format": "markdown", "content": "<text>", "origin": "provided" }` for supplied text) without alteration for auditability.
- Historical scans may retain `<context_dir>/threat_model.md`; read it only when the canonical model is absent, without renaming or rewriting the historical file. For sealed scans, the historical document must be a recorded artifact with a matching digest.

End each repository-scoped threat model with these two lines:

- `Repository: <target_id>`
- `Version: <revision for an immutable Git tree; snapshot digest otherwise>`

## Finding Discovery (Phase 2) Paths

### Deep Rounds And Compact Diff Discovery

A repository scan writes its findings and review state straight into the unsealed canonical files (`findings.json`, and `scan.reviewState` in `scan-manifest.json`). A deep scan runs complete repository-scan rounds. Each round saves findings and pending review work in its checkpoint as it works, then returns its final validated findings, review state, threat model, and optional scope as `result.json`. Pending candidates keep their original evidence in `reviewState.deferred`. A checkpoint alone is never an accepted complete round result.

After each batch of rounds the coordinator compares the repairs described in the reports. It checks disputed pairs that share an assigned repair, or cite overlapping code when a repair could not be assigned. It merges such a pair only when one narrow edit covers both reports in full and each supplies supporting code. A finding with an additional faulty operation or insufficient evidence stays separate. Each original finding and its citations stay in the retained union. The coordinator records comparison failures and keeps unresolved reports. It writes the parent's unsealed `scan-manifest.json` and `findings.json` with the accepted results and their review state; it does not rerun validation or attack-path phases or author a second draft. If the time limit arrives before a round finishes, the parent retains the reason and any saved findings or pending review. See `scan-contract.md` for field definitions. Diff scans retain the compact artifacts described below.

- A diff scan writes raw candidates to `<discovery_dir>/raw_candidates.jsonl` and normalizes them once into `<discovery_dir>/candidates.jsonl` with `normalize_candidates.py`; read the normalized set from that file.
  - Normalization validates candidates against assigned source paths, merges rows with the same CWE ids, locations, and optional instance, preserves their text, and assigns deterministic `candidate_id` values.
  - After normalization, compact validation adds exactly one `validation` object to every row with `disposition` (`reportable`, `suppressed`, `not_applicable`, or `deferred`), `method`, `confidence` (`high`, `medium`, or `low`), `confidence_rationale`, concise `rubric` and `evidence`, `counterevidence_or_proof_gap`, `remaining_uncertainty`, and optional `artifact_paths`. Add `source`, `control`, `sink`, or `preconditions` only when they clarify or differ from the discovery fields.
  - Compact attack-path analysis adds exactly one `attack_path` object to each validation row marked `reportable` or `deferred`, with `decision` (`reportable`, `ignore`, or `deferred`), `dataflow`, `reachability`, `counterevidence`, `impact` and `likelihood` (`high`, `medium`, `low`, `ignore`, or `unknown`), `severity` (`critical`, `high`, `medium`, `low`, `ignore`, or `unknown`), `severity_rationale`, `change_conditions`, and `proof_gap` when deferred. A `reportable` decision requires severity `critical`, `high`, `medium`, or `low`; `ignore` requires severity `ignore`; `deferred` uses a provisional reportable severity or `unknown`.
  - Append all validations and all eligible attack-path decisions as receipts in `<findings_dir>/<candidate_id>/candidate_ledger.jsonl`. Preserve every discovery field and the candidate order from `candidates.jsonl`.
- Optional compact validation evidence: `<discovery_dir>/validation_artifacts/<candidate_id>/`
  - Create this directory only for actual PoCs, crafted inputs, or logs and reference those paths from the row's `validation` object. Do not create placeholder per-candidate directories or narrative reports.

The worklist, per-finding receipt, and phase-report paths below apply to diff workflows. Repository and deep scans assemble validated findings directly, without persisted candidate ledgers or per-finding receipts.

### Diff Discovery And Coverage

- Advisory seed research: `<context_dir>/seed_research.md`
- Changed source input: `<discovery_dir>/rank_input.jsonl`
- Scoped deep-review input: `<discovery_dir>/deep_review_input.jsonl` if applicable
- Finding discovery report: `<discovery_dir>/finding_discovery_report.md`

### Deep Review

- Scoped work ledger: `<discovery_dir>/work_ledger.jsonl` if applicable
- Scoped raw candidates: `<discovery_dir>/raw_candidates.jsonl` if applicable

### Candidate Reconciliation

- Compact Diff candidate ledger: `<discovery_dir>/candidate_ledger.jsonl`
- Standalone or legacy Diff candidate findings directory: `<findings_dir>/`
- Standalone or legacy Diff per-finding directory: `<findings_dir>/<candidate_id>/`
- Standalone or legacy Diff per-finding candidate ledger: `<findings_dir>/<candidate_id>/candidate_ledger.jsonl`
- Scoped dedupe report: `<reconciliation_dir>/dedupe_report.md` if applicable
- Scoped deduped candidates: `<reconciliation_dir>/deduped_candidates.jsonl` if applicable

### Coverage

- Repository-wide coverage ledger: `<coverage_dir>/repository_coverage_ledger.md`
  - This is a coverage artifact, not a findings list: it should include checked surfaces with not_applicable, suppressed, deferred, or reportable dispositions.

## Validation (Phase 3) Paths

Repository scans and deep-scan rounds include validation directly in their final finding semantics. Diff scans record validation as a `validation` receipt per candidate and may use the optional compact evidence path above. Standalone diff workflows may also use these paths:

- Scan-level validation summary: `<findings_dir>/validation_summary.md` if applicable
- Per-finding validation report: `<findings_dir>/<candidate_id>/validation_report.md`
- Per-finding validation artifacts: `<findings_dir>/<candidate_id>/validation_artifacts/`

## Attack-Path Analysis (Phase 4) Paths

Repository scans and deep-scan rounds include attack-path analysis directly in their final finding semantics. Diff scans record attack-path decisions as an `attack_path` receipt per eligible candidate. Standalone diff workflows may also use these paths:

- Scan-level attack-path analysis report: `<findings_dir>/attack_path_analysis_report.md` if applicable
- Per-finding attack-path analysis report: `<findings_dir>/<candidate_id>/attack_path_analysis_report.md`

## Final Report Paths

All paths below are relative to the scan directory.

| Output | Path |
| --- | --- |
| Canonical scan receipt and findings | `scan-manifest.json` and `findings.json` |
| Readable report | `report.md` |
| Threat model, when recorded | `threatmodel.md` |
| Optional detailed finding write-up and supporting files | `findings/<slug>/<slug>.md` and `findings/<slug>/poc/` |
| Optional structural hardening portfolio | `hardening/hardening.md` and supporting files under `hardening/` |
| Report validation notes when validation fails | `report_validation.md` |
| Legacy coverage document | `coverage.json` only when referenced by the manifest's `scan.coverageRef` |
| Finalization recovery checkpoint | `checkpoint-head.json` and `checkpoints/<sha256>.json` (written by the finalizer) |

The current manifest stores additional excluded paths in `scan.review.excludedPaths`. See `scan-contract.md` (Canonical Documents and Review state) for the shapes.

### Draft submission and retrieval

- Unsealed canonical draft: `scan-manifest.json` (with `scan.mode` and `scan.reviewState`) and `findings.json`. No `coverage.json`.
- Deep round result: `artifacts/02_discovery/rounds/round-<k>/result.json` with `findings`, `reviewState`, optional `scope` and `threatModel`; the coordinator writes the aggregated parent draft.
- In-flight checkpoint: `checkpoint-findings.json` and `artifacts/02_discovery/worker-<label>.json`.
- Completed results: the sealed `scan-manifest.json` plus the generated `report.md`.

## Fix Finding Paths

- Fix report, when using an existing scan artifact directory: `<artifacts_dir>/fix_report.md`

## Placement Rules

- Put scan phase outputs and supporting evidence under the numbered artifact subdirectories above.
- Keep fix-finding outputs outside the numbered scan phases because fix-finding can run standalone or against an existing scan.
- Do not author the final `report.md` directly. Put complete scan-level report semantics in the canonical JSON files. Detailed per-finding prose in `findings/<slug>/<slug>.md` and derived design guidance under `hardening/` are optional for every scan mode. Finalization deterministically writes the unsealed `report.md` projection and links any recorded write-ups and hardening portfolio. Do not add these derived documents to the sealed artifact list.
- Keep the full scan bundle together under `scan_dir`.
