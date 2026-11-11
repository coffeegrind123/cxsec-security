# Final Scan Results

The canonical inputs are `scan-manifest.json` and `findings.json`. `finalize_scan_contract.py` validates and seals those documents and the evidence receipts, then projects `report.md`. Do not author or repair that report, parse it back into findings, or use it to fill gaps in canonical evidence. Retained files follow `scan-artifacts.md`.

## Ownership And Submission

| Caller | Writes | Completion owner |
| --- | --- | --- |
| Repository scan (mode 1) or diff scan (mode 2) | The unsealed draft: `scan-manifest.json` (with `scan.mode` and `scan.reviewState`) and `findings.json` under `<scan_dir>` | The parent runs the finalizer once the complete draft exists |
| Deep-scan round (mode 3) | `<discovery_dir>/rounds/round-<k>/result.json` with `findings`, `reviewState`, optional `scope` and `threatModel` | The deep coordinator |
| Deep-scan coordinator | The parent's unsealed draft, aggregated from accepted rounds | The coordinator runs the finalizer |

Author the draft by hand under `<scan_dir>`. Omit `scan.sealedAt`, `scan.artifacts`, `scan.review`, and each active finding's `findingId`, `occurrenceId`, and `fingerprints`; the finalizer supplies the seal, artifact digests, the review summary, and derived identities. New scans write no `coverage.json`. While the scan runs, checkpoint saved findings, pending candidates, and the threat model to `<scan_dir>/checkpoint-findings.json` (the equivalent of an upstream `complete: false` draft); a checkpoint does not claim completed review.

Once the complete unsealed draft is written, finalize:

```bash
python3 $CXSEC_HOME/scripts/finalize_scan_contract.py --scan-dir <scan_dir> --source-root <repo_root>
```

then read the sealed `scan-manifest.json` and the generated `report.md`. Finalization validates existing artifacts; it does not perform missing phases or create an absent draft. Do not claim completion until finalization succeeds and the generated report exists.

## Finding Semantics

Use `$CXSEC_HOME/schemas/tools/scan-draft.schema.json` for new drafts and `finding-detail-fields.md` for rich fields. Supply:

- An evidence-supported lowercase vulnerability-family `ruleId`, `taxonomy.category`, known `taxonomy.cwe` values (or `[]`), and genuine `provenance.source`. Use `local_plugin` only for findings this skill discovered; preserve worker/source provenance and candidate identity.
- Verified source locations, including the broken control or sink and materially affected entry points or concrete implementations. Preserve independently vulnerable instances. Group observations only when they share the broken control and remediation, not merely a CWE.
- A concise summary, root cause, validation basis, attacker dataflow and reachability, calibrated severity and confidence, counterevidence, and practical remediation. Classify by the primary broken control; describe secondary impacts without inventing additional vulnerabilities.
- Nonempty exact snippets in `codeEvidence` when supplied, with valid evidence references. Write entries with the required `id`, `label`, `path`, `startLine`, `code`, and `explanation` fields (`endLine`, `language`, `role` optional). Use `code`, never `snippet`, and `rootCause`, never `root_cause`. Retain the analysis and code that establish the claim rather than repeating a location table in prose.
- `severity.changeConditions` as one nonempty string when present; combine multiple attack-path change conditions into that string. Keep `remediation` a string; `remediationTests` and `preventiveControls` are arrays of strings.

Use `scope` for reviewed context, artifacts, runtime/test status, validation mode, and limitations. If the threat model was generated rather than supplied, say so in the scope context. Preserve the completed canonical `threatModel`, including source citations and uncertainty; do not reconstruct it from the final findings. A supplied or completed Markdown model is retained as `{ "format": "markdown", "content": "<exact model text>" }`. A historical context file can supply missing content but must not replace a newer canonical model.

The generated `report.md` counts informational findings and omits their details. Read those findings in `findings.json` or export them as SARIF or CSV.

## Review State And Pending Work

Keep unfinished requested work and essential in-scope proof gaps in `reviewState.deferred`. Retain optional follow-up in `reviewState.openQuestions`. These notes are checkpoint bookkeeping, not measured file coverage, and do not change the scan execution outcome. The exact shape and the finalizer's requirements (every surface needs an `id` and `receiptRefs`, possibly `[]`; listed receipts must exist under `artifacts/`) are in `scan-contract.md` (Review state).

Drafts use `{ surfaces, explicitExclusions, deferred }`; there is no `completeness` field. Give surfaces meaningful labels and schema-defined dispositions, preserving saved surface IDs in updates. Retain reasons and evidence for rejected, not-applicable, and follow-up work. Open questions may be strings or `{ question, followUpPrompt? }` objects. An open question does not prevent the configured review from finishing. The sealed manifest keeps only the exclusion patterns, so put any limitation a reader must see into `scope` limitations or the final response.

Preserve each saved deferred `id` or `candidateId`, and use each deferred ID only once. Omitting a saved task from the final draft does not by itself close it. Close a generic saved task in the final repository or diff draft by moving it out of `deferred` into `reviewState.resolvedDeferred: [{ id, reason }]`; keep unfinished tasks deferred and update linked surfaces by ID. Candidate-linked tasks close through findings or terminal dispositions. A deep coordinator cannot close a round's tasks; earlier checkpoints remain unchanged.

Do not add reviewed-surface tables or file-coverage claims to the report. Do not put host-owned fields (`mode`, `includePaths`, `excludePaths`, `inventoryStrategy`, `scanId`, `receiptRefs` at the top level) inside `reviewState`; scope paths belong in `scan.scope` and the mode in `scan.mode`.

For diff candidates, read `<discovery_dir>/candidates.jsonl` and each `<findings_dir>/<candidate_id>/candidate_ledger.jsonl`. Map each `validation` receipt into the finding's validation fields and top-level `confidence.level` and `confidence.rationale`, and each `attack_path` receipt into dataflow, reachability, severity, and change conditions. Map recorded outcomes in this order:

1. Validation `reportable` and attack-path `reportable`: finding, with its distinct instance and all relevant locations.
2. Either phase `deferred`: `needs_follow_up` surface and a `reviewState.deferred` entry with the proof gap.
3. Validation `not_applicable`: `not_applicable` surface.
4. Validation `suppressed` or attack-path `ignore`: `rejected` surface.

A missing required phase record remains unresolved with its available evidence. Do not add another reconciliation pass or duplicate phase receipts. Preserve ledger candidate traceability and outcomes; do not drop an exact seed because a same-family neighbor survived.

## Optional Documents

Detailed vulnerability write-ups and hardening proposals are derived, unsealed outputs, not prerequisites for completing a scan. When produced within a running scan, record `finding.writeup.reportPath` as `findings/<slug>/<slug>.md` and `scan.hardening.portfolioPath` as `hardening/hardening.md` in the draft before finalizing. The renderer supplies their links and presentation. Do not add them to the canonical seal or infer that design guidance fixes a finding. Later requests write standalone documents beside the sealed scan rather than editing sealed results.

## Errors And Recovery

When the finalizer rejects named semantic paths, no seal happened. Correct only the named paths in the same draft, preserving all valid findings, fields, evidence, and deferred work, then rerun it; retry at most twice. Do not repeat an unchanged failing run, and stop after the first successful finalization.

For any other required phase, artifact write, or on-disk existence check that fails, or a finalizer failure that is not a named-field rejection, preserve and report the exact diagnostic. Do not claim a final report, a no-findings conclusion, or a successful structured result while completion remains unresolved. Leave `<scan_dir>` intact for a later continuation rather than recording the scan as failed merely because assembly is blocked.

On explicit cancellation, stop additional model work. Use retained results, distinguishing validated findings from pending candidates and recording incomplete scope. A stopped scan with no findings is not a clean-scan conclusion.

## Response

Link the generated `report.md` as the primary readable result. Mention material limitations and specific follow-up work; offer export, patching, or tracking only when relevant to the request. Do not initiate additional external actions or scans without authorization.

Token usage is not measured here. Say that it could not be measured rather than reporting zero or estimating a cost. Usage metadata is never a reason to modify sealed scan artifacts or the deterministic report.

## Review Directives (optional structured output)

When the user asks for structured per-finding output, emit one `::code-comment{...}` directive per surviving finding in the final response. The markdown report and review directives should agree on title, file, line range, and core explanation.

Map the final report severity to directive priority only when emitting the directive:

- `critical` -> `P0`, `priority=0`
- `high` -> `P1`, `priority=1`
- `medium` -> `P2`, `priority=2`
- `low` -> `P3`, `priority=3`

For each reportable finding, emit a review directive in this form:

`::code-comment{title="[P1] Example title" body="One-paragraph review explanation." file="/absolute/path/to/file" start=10 end=12 priority=1 confidence=0.55}`

Directive requirements:

- `title`, `body`, and `file` are required
- `title` should include the mapped directive priority, formatted like `[P1] Example title`
- `file` should be an absolute path
- `start` and `end` should be tight 1-based line numbers
- `priority` should match the mapped directive priority
- `confidence` should be numeric when available
- emit one directive per finding and none when there are no findings
- inline Markdown code spans are allowed and encouraged for short identifiers, flags, function names, and config keys, such as `git -c`, `--config`, and `diff.external`
- do not put double quote characters inside quoted attribute values, including escaped quotes like `\"`; rewrite quoted command examples without quotes or leave them only in the markdown report
