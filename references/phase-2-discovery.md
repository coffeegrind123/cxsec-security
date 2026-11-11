<!-- when-to-use: Use when already in the finding-discovery phase of a security scan or the user explicitly asks to discover candidate security findings in a repository or code change. Do not use as the primary trigger for full PR, commit, branch, patch, or repository scans. -->

# Security Finding Discovery

Identify technically plausible security vulnerabilities in the authorized source, using the threat model and applicable security policy. Discovery preserves evidence for later validation; it does not decide final severity.

Use the path conventions in `scan-artifacts.md` and read `security-guidance.md` before source review. Resolve applicable policy for each reviewed path, including delegated assignments. Honor explicit input and output paths; ask for an explicitly required input only when its absence prevents the requested analysis.

## Select the Workflow

**Repository scans (mode 1) and deep-scan rounds (mode 3) discover inside their own `core-scan.md` audit; neither invokes this phase.**

- **Diff scan (mode 2):** use `scan-artifacts-and-ledger.md` for the changed-file worklist (`generate_rank_input.py make-diff-rank-input`, then `copy_deep_review_input.py`), review every worklist file, write raw candidates to `<discovery_dir>/raw_candidates.jsonl`, and normalize them once into `<discovery_dir>/candidates.jsonl` with `normalize_candidates.py` (see `workbench-file-protocol.md`).
- **Standalone repository discovery:** apply the evidence criteria below to the authorized source and return the candidates and coverage limitations. Do not start a scan or run the diff worklist pipeline.

For a diff, inspect the actual changed behavior, including deleted files at the baseline revision. Treat the commit message and title as possibly incomplete or misleading. Follow supporting code far enough to understand the affected boundary; expand to sibling callers when a changed shared control affects them. Do not broaden into an unrelated repository audit.

## Evidence Criteria

- Trace attacker-controlled input or a privileged operation through the closest relevant control to the sink and security impact. Explain why the control is absent, bypassable, or applied to the wrong value or boundary.
- Check runtime reachability and deployment assumptions. Record effective guards and containment as counterevidence; a safe sibling implementation does not establish that the candidate path is safe.
- Preserve the root-control location as well as entrypoints, wrappers, concrete implementations, and sinks needed to understand the claim. When the claim covers several implementations, inspect those implementations rather than asserting that all are affected.
- Keep independently reachable vulnerable instances addressable. Merge duplicate observations of the same source/control/sink/impact instead of splitting cosmetic variants; retain all affected locations and original candidate IDs when merging.
- Follow explicit user or advisory seeds to their exact source and control. Record the evidence that supports, disproves, or leaves the seed unresolved; a nearby issue in the same family does not close it. Use only authorized source material and do not fetch advisory links without permission.
- Distinguish concrete security impact from maintainability or robustness concerns. A crash, dangerous API, optional feature, or missing check is a lead, not a finding by itself. Carry plausible candidates with explicit proof gaps to validation rather than inventing evidence or discarding them for lack of a runnable reproduction.

Divide independent review assignments among `Agent` subagents when useful, with the target, scope, relevant policy/model, and required result fields in a self-contained prompt. The parent reviews unassigned work and reconciles duplicates. Do not repeat validation or attack-path phases inside discovery.

## Candidate Output

For each candidate, retain:

- Stable candidate ID and title; preserve supplied seed or ledger IDs and advisory references.
- Affected file/line locations, labeling `entrypoint/wrapper`, `root_control`, `sink`, and `concrete_implementation` where useful.
- Attacker-controlled source, closest control, sink or broken control, plausible impact, and the source evidence connecting them.
- Counterevidence, deployment preconditions, unresolved questions, and what validation needs to establish.
- CWE IDs when known, otherwise an empty list.
- For repository or scoped-path instances, an instance key `<family>:<file>:<line>` when required by the caller.
- For diff findings, `relevant_lines` only where relevant buggy behavior overlaps the diff.

For a diff scan, save the discovery report to `<discovery_dir>/finding_discovery_report.md` and append one discovery receipt per candidate to `<findings_dir>/<candidate_id>/candidate_ledger.jsonl` (shape in `workbench-file-protocol.md`); subsequent phases own their own evidence and receipts. Finish when assigned source review and concrete follow-ups are accounted for, recording unfinished review honestly. If no plausible candidates remain, return that result with the actual reviewed scope and limitations.
