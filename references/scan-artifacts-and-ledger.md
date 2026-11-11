# Diff Worklists and Artifacts

Use this reference for diff discovery (mode 2). Repository scans (mode 1) and deep scans (mode 3) do not use it. Follow `scan-artifacts.md` for paths.

## Changed-file Worklist

Generate `rank_input.jsonl` from every changed text file, including deleted files. Tracked changes remain in scope regardless of ignore rules; local patches also include non-ignored untracked files.

```text
<python_command> $CXSEC_HOME/scripts/generate_rank_input.py make-diff-rank-input --repo <repo_root> --base <base> --mode revisions --head <head> --out <discovery_dir>/rank_input.jsonl
<python_command> $CXSEC_HOME/scripts/generate_rank_input.py make-diff-rank-input --repo <repo_root> --base <base> --mode local-patch --out <discovery_dir>/rank_input.jsonl
```

Choose the first command for PR, commit, or branch diffs, and the second for a local patch. Pass the full commit object IDs resolved for the scan target, not revision expressions, and keep the exact baseline and target unchanged.

Copy every row to the review worklist; diff scans do not rank or drop changed files:

```text
<python_command> $CXSEC_HOME/scripts/copy_deep_review_input.py --rank-input <discovery_dir>/rank_input.jsonl --out <discovery_dir>/deep_review_input.jsonl
```

`copy_deep_review_input.py` is a carried local addition (upstream moved `copy-deep-review-input` into its launcher). The legacy ranking helpers are gone upstream: `make-repo-rank-input`, `select-deep-review-input`, `make-rank-shards`, `validate-rank-shard`, `merge-rank-outputs`, `make-rank-pool-plan`, `validate-rank-worker`, and `validate-rank-pool`. Explicit repository scopes use `generate_rank_input.py make-repo-scope-input --repo <repo_root> --scopes-file <scopes_json> --out <output_jsonl>`.

## Scoped Deep Review

Review each worklist file, using its baseline contents when deleted. Read supporting files only as needed to explain changed security behavior, and record why they were included. Cover the file's security-relevant behavior rather than treating a search hit as completed review.

Use `Agent` subagents for independent assignments when useful. Size assignments around coherent behavior and review complexity, within available capacity. If delegation fails, the parent reviews unstarted work. Subagent prompts must be self-contained: they carry the exact scan instructions they follow and do not inherit this reference, another phase reference, or the parent's context.

Each assignment needs the target and diff range, assigned paths, applicable security policy and threat model, relevant user seeds, and output locations. Workers return reviewed paths and limitations, candidates with source/control/sink/impact evidence, counterevidence, and open validation questions. Discovery does not require validation or attack-path results before a candidate can be returned or deduplicated. Subagents are read-only on the target code; they may write only the scan artifacts named in their prompt.

## Coverage and Phase Handoff

The parent reconciles assigned paths against the worklist. Retain a concise completion or limitation for each row in `<discovery_dir>/work_ledger.jsonl`; do not manufacture coverage for unread files. Preserve explicit advisory seeds and their evidence or unresolved questions in `<context_dir>/seed_research.md` when seed research is part of the request. Supplied context does not authorize additional source access.

For retained candidates, use stable IDs and a discovery receipt in `<findings_dir>/<candidate_id>/candidate_ledger.jsonl` (shape in `workbench-file-protocol.md`). Each receipt identifies the scope, locations, evidence, and discovery status. Save the discovery result in `<discovery_dir>/finding_discovery_report.md`.

When combining several reviewers, retain `raw_candidates.jsonl` to preserve their results, and normalize once with `normalize_candidates.py` (see `workbench-file-protocol.md`). Merge duplicate observations before further analysis, preserving raw IDs and affected locations in `<reconciliation_dir>/deduped_candidates.jsonl`; use `<reconciliation_dir>/dedupe_report.md` only when the merge needs explanation. Independently vulnerable instances remain addressable.

Validation and attack-path analysis belong to their respective phases. Their owners add the method, evidence or proof gap, disposition, and phase receipt to the existing candidate record. Reuse completed analysis rather than rerunning it to satisfy another ledger. Final reporting must account for every candidate as resolved or explicitly deferred; a standalone discovery request ends at the discovery handoff.
