# Sealed Scan Contract

This contract defines the canonical machine-readable documents for scans that reached a sealed terminal outcome and their readable markdown report projection.

## Canonical Documents

Open the current example manifest `$CXSEC_HOME/examples/completed-scan/scan-manifest.json` alongside its `findings.json` and readable `report.md` in the same directory.

| File or field | What it contains |
| --- | --- |
| `scan-manifest.json` | Immutable receipt with scan ID, target, scope, mode, terminal status, seal time, and artifact digests. |
| `findings.json` | Semantic finding records retained at the terminal outcome. The manifest's `scan.findingsRef` points to this file. See `finding-detail-fields.md` for optional evidence and analysis. |
| `scan.review` inside the manifest | Additional excluded paths (`excludedPaths`). |
| `report.md` | Human-readable report generated from the canonical JSON. `sarif-adapter.md` explains which fields survive export. |

See `scan-artifacts.md` (Final Report Paths) for the complete directory layout and optional outputs.

New scans do not write `coverage.json`. For a legacy manifest with `scan.coverageRef` (example: `$CXSEC_HOME/examples/legacy-completed-scan/`), read the referenced coverage document alongside the findings. Check for this field before opening a separate coverage file. Keep detailed evidence in scan-local artifacts and reference it from the canonical summaries.

Optional structured finding details are part of each semantic finding record, not a projection parsed from a readable report. Generated exports such as SARIF are downstream projections, not part of the canonical semantic source of truth.

Deep-scan SARIF results and CSV rows preserve their existing instance-level presentation and add only the canonical candidate id needed to group child reports. Standard-scan CSV presentation remains unchanged.

This bundle records immutable scan observations. It is not a workflow-state database. Consumers must store mutable annotations, lifecycle decisions, external links, retention policy, and synchronization state separately.

Retention is an explicit consumer decision. Producing a sealed bundle must not silently copy it into an archive.

## Manifest Semantics

The manifest records the terminal timestamp and a SHA-256 digest for each file listed in `scan.artifacts`. Each path appears exactly once. The current example lists `findings.json` alone. A legacy bundle also lists its referenced coverage file, and scans that retain immutable evidence receipts (every `receiptRefs` path in the review state) list those files too. The manifest carries these digests and does not hash itself. Adapters read the sealed files and write reports or exports separately from the seal; they must not mutate the sealed manifest or canonical documents.

Producers should use UTC ISO 8601 timestamps in the native SDK or plugin format. All schema-valid fractional widths remain readable on supported Python versions; parsing uses native microsecond precision. History and finding queries use native date precision and stable ID tie-breakers; ordering beyond millisecond precision is not guaranteed. Stored timestamp text remains unchanged.

`scan.status` records why the bundle was sealed:

| Status | Meaning |
| --- | --- |
| `completed` | The requested scan reached normal completion. |
| `failed` | The scan stopped after an unrecoverable failure; retained artifacts may be partial. |
| `canceled` | The scan stopped after an explicit cancellation; retained artifacts may be partial. |
| `interrupted` | The scan stopped before normal completion because execution was interrupted; retained artifacts may be partial. |

Only `completed` supports a completed-scan conclusion. For every stopped outcome, consumers must preserve retained findings and review state while treating absence of findings as inconclusive.

Optional `scan.warnings` (a list of strings) records run-level diagnostics available when the bundle is first sealed. SARIF exports include these messages alongside deferred-task reasons in `toolExecutionNotifications`; warnings do not change `executionSuccessful`, which follows `scan.status`. Missing or empty warnings add no notifications. Existing sealed bundles remain unchanged, and export warnings discovered afterward are reported separately, not written into the seal. Deferred-task reasons in the draft `reviewState` are not carried into the sealed manifest, so a file-authored draft that needs them in SARIF must also list them in `scan.warnings` (see `sarif-adapter.md`).

### Stopped Result Recovery

Upstream recovers a stopped scan from its SQLite workbench. This port keeps scan
state in files, so recovery is reading what the interrupted scan already wrote:
`<scan_dir>/checkpoint-findings.json`, any `<discovery_dir>/worker-*.json` or
`<discovery_dir>/rounds/round-*/result.json`, and the candidate ledgers. Report
those retained results with their remaining work and original evidence.

Only admit work that was actually finished before the stop. A checkpoint is not a
validated finding, and a partial round result is not an accepted round. After an
explicit cancellation, do not admit artifacts written after the cancellation
point.

## Target Snapshots

Choose the target kind based on the reviewed content, not the scan invocation:
`git_worktree` for a checked-out Git workspace, `directory_snapshot` for a non-Git directory, `git_diff` for a Git-backed change set, and `git_revision` for an exact immutable Git tree.

When `<scan_dir>/scan-context.json` already records the resolved target, use it instead of re-inferring the kind from the checkout.
A clean Git checkout has `allowedKinds: ["git_revision"]`: use its recorded revision and omit `snapshotDigest`.
A dirty checkout has `allowedKinds: ["git_worktree"]`: copy `requiredSnapshotDigest` exactly.

| Kind | Required snapshot fields |
| --- | --- |
| `git_revision` | `revision` |
| `git_worktree` | `revision` when available and `snapshotDigest` |
| `git_diff` | `snapshotDigest`; include `baseRevision` and `headRevision` when available |
| `directory_snapshot` | `snapshotDigest` |

`targetId` identifies the stable repository or workspace. Prefer a digest of a sanitized canonical absolute remote URL when one exists. Otherwise use a digest of a stable local workspace identity. Never persist remote URL credentials, query parameters, fragments, or tokens.

For dirty worktrees and working-tree diffs, calculate `snapshotDigest` from a deterministic representation of the reviewed content, including staged changes and reviewed untracked files where applicable. For committed or revision-range diffs, derive it from the exact authoritative diff kind and immutable base/head revisions. For directory snapshots, hash a sorted relative-path and file-hash inventory of the reviewed scope. Encode the result as `codex-security-snapshot/v1:sha256:<64 lowercase hex characters>`.

## Finding Identity

Each authored finding includes:

- stable `ruleId`: vulnerability class or generated rule family
- stable `identity.anchor`: semantic root-control anchor
- optional `identity.instance`: independently attackable sibling instance

Use lowercase slugs for all three values. Keep them stable across nearby line movement and file renames. Finalization derives:

- `fingerprints.primary` from target ID, rule ID, anchor, and instance
- `findingId` from the fingerprint
- `occurrenceId` from scan ID and fingerprint

Do not put line numbers in `identity.anchor`. When two sibling vulnerabilities share a rule and semantic anchor, give them distinct stable `identity.instance` values.

Fingerprint matching is a reconciliation signal, not proof that two findings are equivalent. Treat ambiguous matches as unresolved.

When a finding has multiple affected locations, label the vulnerable control location `root_control` when one is known. Adapters keep the first `root_control` location first and otherwise fall back to the first affected location, while preserving every distinct entrypoint, wrapper, sink, concrete-implementation, and code-evidence occurrence as a matchable location.

## Rule ID Policy

`ruleId` identifies a stable vulnerability family, not a per-scan finding.
Prefer:

`<primary-category>.<stable-control-family>`

Examples:

- `path-traversal.archive-extraction`
- `authorization-bypass.object-update`
- `sql-injection.query-builder`

Use CWE taxonomy separately. Do not include file names, line numbers, scan IDs, or display numbering in `ruleId`.

## Review state

New scans publish `scan-manifest.json` and `findings.json` only. The manifest owns scan identity, `scan.mode`, and the configured scope. After sealing, `scan.review` contains only `excludedPaths`, used when comparing scans. These values do not measure the percentage of files read.

A Deep parent retains the configured paths and notes from accepted reviews. Round labels distinguish each review's surfaces and deferred items. Receipt references point to the original evidence. Merging duplicate findings preserves pending review work. If the time limit arrives before a round finishes, keep valid checkpoint findings and pending work with the deadline reason. See Stopped Result Recovery.

Put `reviewState` inside `scan` in the unsealed manifest, and always set `scan.mode` (finalization otherwise defaults it to `repository`). Finalization stores the full state in `<scan_dir>/checkpoints/` (pointed to by `checkpoint-head.json`) for recovery, hashes every `receiptRefs` file into `scan.artifacts`, and replaces the draft state with the small `scan.review` summary. Exclusion reasons and surface notes are not carried into the sealed manifest or `report.md`; keep anything a reader needs in the findings, the scope `limitations`, or the visible final response.

```json
"reviewState": {
  "surfaces": [
    {"id": "archive-import", "label": "Archive import extraction", "disposition": "reported",
     "riskArea": "Path traversal", "notes": "Extractor and path join reviewed.",
     "receiptRefs": ["artifacts/02_discovery/archive-import-notes.md"]}
  ],
  "explicitExclusions": [{"pattern": "tests/fixtures/**", "reason": "Synthetic fixtures"}],
  "deferred": [{"id": "auth-refresh", "reason": "Refresh flow needs runtime tracing", "surfaceIds": ["archive-import"]}],
  "openQuestions": [{"question": "Is the importer reachable unauthenticated?", "followUpPrompt": "Trace the import route's auth."}]
}
```

`surfaces`, `explicitExclusions`, and `deferred` are required (use `[]` when empty). Every surface needs a stable `id` (lowercase, `^[a-z0-9][a-z0-9._/-]*$`), `label`, `disposition`, and `receiptRefs`; the finalizer rejects a surface missing `id` or `receiptRefs` even though the draft schema marks them optional, so write `receiptRefs: []` when there is no retained receipt. Each listed receipt must already exist as a regular non-symlink file under `<scan_dir>/artifacts/`, or finalization fails. Optional `resolvedDeferred` entries close saved generic deferred tasks by `id` and `reason` on final Standard or diff drafts. Do not put `mode`, `includePaths`, `excludePaths`, `inventoryStrategy`, `receiptRefs`, `scanId`, `documentType`, or `schemaVersion` at the top level of `reviewState`; the draft schema forbids them, and finalization silently overwrites them from `scan.mode` and `scan.scope`.

Comparison uses the later scan's execution status, configured scope and additional exclusions before classifying an absent finding as resolved.

### Scan modes and inventory

`scan.mode` (or `mode` in a legacy coverage document) records the requested scan workflow:

| Mode | Meaning |
| --- | --- |
| `repository` | Repository-wide scan |
| `scoped_path` | Scan limited to explicitly requested paths |
| `diff` | Git-backed change-set scan when no more specific mode applies |
| `commit` | Commit compared with its resolved baseline |
| `branch_diff` | Branch or pull-request change set compared with its baseline |
| `working_tree` | Staged or unstaged local changes |
| `deep_repository` | Exhaustive repeated repository-wide scan |

In a legacy coverage document, `inventoryStrategy` records how the producer enumerated the reviewed content:

| Inventory strategy | Meaning |
| --- | --- |
| `repository` | Repository-wide file inventory |
| `scoped_path` | Repository inventory constrained to requested paths |
| `diff` | Files selected from the reviewed Git change set |
| `directory` | Deterministic non-Git directory inventory |
| `custom` | Producer-defined inventory described by detailed receipts |

The discovery helper reads one UTF-8 path per line from `in_scope_files.txt`. It accepts LF and CRLF separators and preserves other whitespace. Filenames containing CR or LF are unsupported. For a whole-repository Deep scan, use `deep_repository` for the mode.

### Detailed review state in drafts, checkpoints, and legacy coverage

These records list reviewed surfaces, exclusions, and follow-up work. There is no `completeness` field. Use the terminal manifest for execution status.

Map detailed ledger closure into completed surface summaries in this order:

| Completed surface condition | Disposition |
| --- | --- |
| At least one `reportable` row | `reported` |
| Otherwise, at least one `deferred` row | `needs_follow_up` |
| Otherwise, at least one `suppressed` row | `rejected` |
| Otherwise, an applicable surface was checked and no candidate survived | `no_issue_found` |
| Otherwise, the surface is not applicable | `not_applicable` |

Record each explicit exclusion with a `pattern` and `reason`. Record each deferred unit with a stable `id`, a `reason`, and optional `candidateId`, `paths`, or `surfaceIds`.

When retained, detailed ledgers live under the numbered scan artifact directories.
Receipt references must point to regular non-symlink files under `artifacts/`.
`scan.review` retains additional exclusions for adapters and comparison. Legacy sealed scans continue to reference their original `coverage.json`.

## Canonical Report Semantics

In the current format, the manifest and findings are the semantic inputs to final report generation. Producers must not author `report.md`; finalization deterministically projects it after validating the canonical seal. The report remains an unsealed downstream projection and can be regenerated without changing canonical JSON or evidence artifacts.

Record report-specific semantics without duplicating data already represented elsewhere:

- `scan.scope`: optional narrative `summary`, reviewed artifact names, runtime/test status, validation mode, scan context, and limitations. Include/exclude paths remain the authoritative scope boundaries.
- `scan.threatModel`: structured summary plus assets, trust boundaries, attacker capabilities, security objectives, and assumptions, or `{ "format": "markdown", "content": "<exact model text>" }` for a retained document. Optional model `scope` and `origin` identify the modeled paths and source separately from the scan's scope. When completed Deep rounds supply different models, the parent retains the first model here and the other models on their round records in the retained draft or checkpoint review state. `finalize_scan_contract.py` derives `<scan_dir>/threatmodel.md` from the primary model; it is an exportable projection, not an independently authored input.
- finding `validation`: validation method, direct evidence, counterevidence, and the conclusion used by the report.
- finding `codeEvidence`: stable, exact source snippets with labels, locations, language, and explanations; `rootCause`, `validation`, and `attackPath` select the snippets they need through `evidenceRefs`.
- finding `rootCause`: the violated invariant and the code that breaks it. Do not substitute a path/line restatement for the explanation.
- finding `attackPath.dataflow`: source, transformations, sink, outcome, and a concise source-to-sink narrative.
- finding `attackPath.reachability`: attacker, entry point, preconditions, outcome, and a concise reachability narrative.
- finding `severity`: the assigned level plus rationale and the concrete evidence that would raise or lower it.
- finding remediation: the existing minimal fix string plus optional tests and preventive controls.

These fields are optional for compatibility with existing v1 canonical artifacts. When omitted, finalization emits explicit, deterministic fallback text derived only from the remaining canonical JSON. It never reads an existing report to recover missing semantics.

## Schemas

New completed findings and the draft `reviewState` must match `$CXSEC_HOME/schemas/tools/scan-draft.schema.json`. Finalization rejects legacy field aliases, malformed optional details, and invalid semantic slugs instead of repairing them. Historical sealed reports are validated through an in-memory compatibility adapter; their saved bytes remain unchanged. Stopped-scan recovery still salvages saved evidence.

- `$CXSEC_HOME/schemas/scan-manifest.schema.json`
- `$CXSEC_HOME/schemas/findings.schema.json`
- `$CXSEC_HOME/schemas/coverage.schema.json` for legacy scans

V1 consumers ignore unknown properties for forward compatibility. Producers must still validate documented fields and should not emit undocumented properties casually.

Representative valid contract examples live under `$CXSEC_HOME/examples/completed-scan/` (current) and `$CXSEC_HOME/examples/legacy-completed-scan/` (legacy, with `coverage.json`).
