<!-- when-to-use: Use when already in the attack-path-analysis phase of a security scan or the user explicitly asks to trace a security finding from source to sink and calibrate severity. Do not use as the primary trigger for full PR, commit, branch, patch, or repository scans. -->

# Security Attack Path Analysis

Determine whether each supplied finding has a supported attacker path, what impact it has, and whether it is reportable. Follow the storage policy in `workbench-file-protocol.md` before creating or retaining files.

## Establish the attack path

For a scan phase, use its per-scan threat model and candidate set from `scan-artifacts.md`. Preserve supplied input paths. If a required scan artifact is unavailable, report the missing input.

For standalone analysis, use the supplied finding, repository, threat model or security policy, and context. A per-scan artifact is not required. State material assumptions and ask for missing context only when it prevents a meaningful assessment.

1. Establish the in-scope attacker, affected product surface, entry point, controlled input, security boundary, and sensitive operation. Trace the path from repository evidence.
2. Identify relevant controls and the strongest counterevidence. Explain what they establish, which prerequisites remain, and whether the exact claimed boundary is crossed.
3. Assess impact and likelihood from those facts. Apply `severity-policy.md` for the final decision. When the scan supplies a severity rubric, use it to grade reportable findings and retain `ignore` for candidates without security impact. Keep facts, severity calibration, and the final policy decision distinguishable in the result.
4. Return an explicit decision for every eligible candidate, including ignored or deferred candidates. Do not replace a supported instance with a neighboring finding or lose its root-control location.

Use repository evidence and explicitly supplied context. Access the network only when the user has expressly authorized it; an offline scan never accesses the network. Do not invent unsupported attack chains. Missing deployment or public-ingress evidence can limit confidence without defeating an otherwise supported finding.

## Scan integration

Repository scans (mode 1) and deep-scan rounds (mode 3) assess attack paths inside their own `core-scan.md` audit; neither invokes this phase.

### Diff scan (mode 2)

- Load the per-scan threat model, the candidates from `<discovery_dir>/candidates.jsonl`, and their validation receipts from each `<findings_dir>/<candidate_id>/candidate_ledger.jsonl`.
- Analyze every candidate whose validation disposition is `reportable` or `deferred`. Preserve candidate identity and existing discovery and validation fields.
- Decide every eligible candidate, then append exactly one `attack_path` receipt per eligible candidate to its ledger in one pass, using the receipt shape in `workbench-file-protocol.md` and the original candidate order. When no candidate enters this phase, record nothing and say so.
- These receipts are the complete phase output. Do not create duplicate reports, receipts, or manual ledgers.

### Standalone phase requests

Use the report and receipt paths in `scan-artifacts.md` (Attack-Path Analysis Paths). Every candidate entering this phase must have an explicit decision and a receipt with its ID, facts or exact proof gap, and report reference. Record ignored candidates before excluding them from the surviving finding set.

For repository-wide or scoped-path requests, include validation closure rows marked `reportable` or `survives: yes`, even if discovery did not assign a polished finding number. Preserve affected entrypoint/wrapper, root-control, sink, and concrete-implementation locations supplied by validation.

## Output

For standalone analysis, follow the caller's format or return a concise assessment per finding. Scan phases use their output contract above. Include:

- title and supplied candidate, instance, and ledger identities;
- precise affected locations and attacker-to-impact steps;
- relevant facts from `attack-path-facts.md`;
- controls, counterevidence, prerequisites, and material proof gaps;
- impact, likelihood, calibrated severity, and final policy decision with their reasons.

Retain enough evidence to explain both surviving and suppressed findings. Apply the severity policy to the established facts rather than reopening discovery or substituting a different attack story.
