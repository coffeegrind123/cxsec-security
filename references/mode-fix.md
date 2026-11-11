<!-- when-to-use: Use when the user explicitly asks to fix and verify a validated or plausible security finding. Do not use as the primary trigger for full PR, commit, branch, patch, or repository scans. -->

# Fix Finding

## Objective

Turn a current security finding into a minimal, validated code change. If the code is already safe, prove that and report that no change was needed.

Classify the current state from evidence, close the broken security boundary, preserve legitimate behavior, and pass the checks required by the selected verification mode. Prefer the smallest repository-native change that meets those requirements.

## Verification Mode

Use `standard` verification unless the caller explicitly selects
`verificationMode: static`. The selected mode applies throughout this mode,
including delegated reviews and workbench stages; pass it to every subagent.

In static mode, assess source and diff evidence only. Do not install dependencies
or run builds, tests, reproducers, or the application, including when validation
instructions request them. Repository-reading tools remain available. State that
runtime checks were not performed; do not count them as passed or require them
for this assessment. Missing runtime tooling alone is not a blocker, but a
material gap in the source evidence still requires `blocked`.

## Patch Contract

Before editing, inspect the affected implementation, its direct callers, nearby
helpers, and relevant existing tests. Establish from repository evidence:

- the attacker-controlled input and concrete source-to-sink path or broken control
- the security invariant and narrowest shared enforcement boundary
- legitimate behavior, APIs, error semantics, and compatibility constraints that must remain
- the closest existing implementation, validation, and error-handling precedents

Treat the finding as a data-flow and boundary problem, not merely the named input
example. Check equivalent encodings, parser forms, aliases, callers, sinks, and
every representation or copy of security-sensitive state that could bypass the
proposed change. Handle unsafe state explicitly; do not silently accept, truncate,
or reinterpret it into another reachable form.

## Implementation Workflow

1. Trace the reported path and inspect only the context needed to identify the real shared boundary. Return `no_change` when repository evidence shows that the reported path is already safe; do not make a speculative change.
2. In standard mode, when feasible, run the smallest high-signal reproduction through that boundary and one legitimate control through the same path.
3. Implement the smallest repository-native fix at the shared boundary. Prefer nearby helpers and established APIs. Do not broaden into unrelated redesign, cleanup, or sibling findings.
4. Before verification, challenge the patch rather than defending it: inspect every direct caller of each changed helper and both outcomes of each changed condition. Look for one sibling path, representation, or copy that still reaches the vulnerable sink and one ordinary or default input that the patch newly rejects or reinterprets; revise the implementation if either exists.
5. In standard mode, verify the resulting change:
   - inspect the final diff and run the narrowest syntax, import, build, or type check relevant to it
   - rerun the security trigger or strongest focused substitute and review one alternate malicious input class
   - rerun the legitimate control, nearest existing tests, and the owning package's applicable required checks

In static mode, use these verification gates instead: inspect the final diff; trace the original exploit path and relevant alternate inputs through the changed control; then inspect callers and existing tests as source to establish that legitimate behavior and compatibility remain intact. Cite the source evidence for each gate and identify anything it cannot establish.

Return `blocked` if the vulnerability may be real, but essential evidence, tooling, access, or a product or compatibility decision is missing, so a safe fix cannot be responsibly completed or verified.

## Review the fix

Challenge the patch for surviving bypasses and regressions in legitimate behavior. Use independent investigation or review when the complexity, uncertainty, or security impact warrants it. Give a fresh read-only reviewer the finding, repository root, authorized scope, repository policy, verification mode, and candidate diff so they can assess it from source without the author's rationale or claimed test results. If delegation is unavailable, perform that review as a separate pass.

Confirm review concerns against source or, in standard mode, focused execution before changing the patch. Address only confirmed issues within the finding and compatibility boundary, then repeat the affected verification gates for the selected mode. Revisit the review when a revision changes the security boundary or introduces a new material risk. Ensure no temporary or unrelated changes remain.

## Workbench Remediation Stages

When the user requests a specific remediation stage, follow only that stage. Record each stage's terminal status and evidence in the fix report, or in the visible response when running standalone. Carry the finding identity, base revision, and patch path and SHA-256 digest across stages yourself; there is no external workbench holding that state. The stage boundary changes when code may be written, but it does not weaken the validation requirements above.

Before creating or entering any work copy, select Python and Git from a controlled empty directory outside all checkouts. Verify that each trusted tool's absolute invocation path, resolved parent directory, and resolved executable are outside the selected target, its enclosing checkout, and all capture and rehearsal workspaces. Use a trusted absolute `PYTHON`, a host-managed runtime, or a verified system interpreter. Invoke its quoted absolute path with `-I` to import helpers from `$CXSEC_HOME/scripts`. From the same directory call `workbench_target.trusted_git_executable(target)`, which honors `CODEX_SECURITY_GIT` or discovers Git when that variable is absent. Pin the verified absolute invocation path it returns in the helper process's `CODEX_SECURITY_GIT` environment and pass it to child helpers. Stop if either tool cannot be verified. For Generate and Apply Git commands, pass `offline=True` and the real target to `workbench_target.git_command`, use `-C` for the working directory, and set `-c core.hooksPath=<empty private directory>`.

Disable external Git filters for inline capture and any rehearsal in either verification mode. Identify drivers with a nonempty `clean`, `smudge`, or `process` command in the effective Git configuration of the real target and each private command's working directory. Write the overrides with `git config --file <file> <key> <value>` using separate arguments. Clear each driver's `clean`, `smudge`, and `process` commands. For staging and capture diffs, set `filter.<driver>.required` to true only if the driver was already required or had a `clean` or `process` command. For a rehearsal that writes files, use a separate override that also requires drivers with a `smudge` command. Pass `-c include.path=<absolute private config>` for the operation's overrides. Git will fail if it needs the driver, including after edits to `.gitattributes`. If capture requires external conversion, register an existing reviewed scan-local patch by path and digest when available, or record the failure.

In static mode the checkout snapshot and reverse check used to register the patch must also preserve source-only verification. Rule out executable filters in the applicable working-tree and index attributes, including any attribute changes in the reviewed patch, before requesting such an operation. Stop before the operation if that cannot be established.

- **Generate.** Before developing or editing the fix in either verification mode, confine filesystem writes by the worker and its child processes to the isolated worktree or temporary workspace, even through filesystem links. Develop the source and regression-test changes and run any permitted tests inside that boundary. Preserve links as link entries. To edit a referent, use a verified path inside the copy. If writes cannot be confined, record `failed` before editing or running repository commands. Record `generated` in the fix report with the patch path and digest.
  - For a Git working tree, isolate the writable private repository from system and user Git configuration starting before `git init`. In the private helper process, remove inherited `GIT_CONFIG` and `GIT_CONFIG_*` variables, use empty private `HOME` and `XDG_CONFIG_HOME` directories, set `GIT_CONFIG_NOSYSTEM=1` and point `GIT_CONFIG_GLOBAL` to an empty private file. Initialize a fresh repository with `git init --template=` and the target's object format (`git rev-parse --show-object-format` where supported). Copy the request's working-tree baseline, including local edits and intended untracked files, preserving file modes, symlinks, the nested target location and applicable in-repository `.gitattributes` files. Exclude source Git metadata, config and hooks. Set only the needed non-executable values such as `core.autocrlf`, `core.eol`, `core.fileMode` and `core.symlinks`. Compare the intended paths' effective attributes using `git check-attr -z --all --stdin` in both repositories. Reproduce needed built-in attributes and selected filter names as data so the private filter overrides apply. Never copy executable filter configuration from the target.
  - Seed the private index with the target's stage-zero blob entries for the intended existing files from `git ls-files --stage -z` at the repository root. Run this inventory with `LC_ALL=C` and stop on an `error:` or `fatal:` diagnostic even if Git exits successfully. Read each blob with `workbench_source_scopes.offline_git_bytes(target, "cat-file", "blob", oid)`. Stop if any blob is unavailable locally. Write the returned bytes with private `git hash-object -w --stdin`, verify its OID, and pass the selected entries to private `git update-index -z --index-info`. Git uses prior blob contents for automatic line-ending conversion.
  - Use `git ls-files --cached --others --exclude-standard -z` in the real target to check that the capture includes every intended existing preimage, including files to delete. Stop if a required preimage is ignored and untracked. Stage the intended existing paths in the copy with `git add -- <paths>` before editing and record `git write-tree` as `BASE`. Before final staging, query the same inventory from the edited copy's selected directory using the original target environment, Git directory and index, with the copy root as `work_tree`. This uses the reviewed `.gitignore` changes and the target's repository and user excludes. Stop if any required surviving file is absent. Stage just the intended paths, including additions, deletions and new regression tests, with `git add -A -- <paths>`. From the selected directory in the copy, capture `git diff-index --cached --binary --relative --no-ext-diff --no-textconv --no-renames --submodule=short --no-color --unified=3 --src-prefix=a/ --dst-prefix=b/ BASE -- .` as bytes.
  - For a target outside Git, copy its baseline to sibling directories `a` and `b` outside every Git repository. Preserve file modes and symlinks and make only the reviewed changes in `b`. Compare their raw contents from the parent in the isolated private Git environment described above, with `GIT_ATTR_NOSYSTEM=1` and no target conversion settings. Capture `git -c core.autocrlf=false diff --no-index --binary --no-prefix --no-renames --submodule=short --no-ext-diff --no-textconv --no-color --unified=3 -- a b` as bytes. Exit 1 means the copies differ.
  - Inspect the entire diff against the intended source changes. For any rehearsal, use a separate disposable baseline with the same nested location and native conversion settings, and confine all writes to that copy even through links. If native conversion could affect a non-Git change, rehearse before registration. Compare the actual forward result under the intended Apply settings to `b`, then reverse under the target's native settings and compare the restored tree to `a`, including raw file bytes. Record `failed` if the reviewed result or baseline cannot be reproduced. Preserve the selected verification mode.
  - Write the exact unified diff bytes, preserving any final newline and any non-UTF-8 bytes, to `<artifacts_dir>/remediation.patch` beside the fix report (see `scan-artifacts.md`), or to a path the user named outside the target checkout when running standalone. Confirm Git can parse it with `git apply --check --stat` against a disposable copy of the baseline, then record its path and SHA-256 digest.
  - For an existing scan-local patch, record its path and digest instead of writing a new one. Reuse the recorded path and digest when retrying a failed Generate request that already has a reviewed patch.
- **Apply**: Verify the recorded base revision and patch digest, then apply exactly that patch to the selected working tree without unrelated edits. Record `applied` or `failed`. Do not verify or close the finding in this stage.
  - For example, consider a private checkout with no executable hooks or filters. Its selected directory is `components/api`. The whole reviewed patch consists of one content hunk editing the existing tracked regular file `handler.py` in place. The checkout uses `core.autocrlf=false`, and no attributes convert `handler.py`'s contents. Both headers name that file, and its ancestors are ordinary source directories. Confirm the current file bytes match the reviewed preimage. With `root, prefix = git_worktree_context(target)`, call `git_command(target, "-C", str(root), "-c", f"core.hooksPath={empty_hooks}", "apply", "--no-index", "--check", "--whitespace=nowarn", f"--directory={prefix}", "-", input_data=patch_bytes, text=False, offline=True)`. If it succeeds, repeat that call with the same digest-verified bytes and omit `--check`. Confirm that `components/api/handler.py` contains exactly the reviewed result. Running from inside `components/api` can exit successfully while skipping the change.
  - For an equivalent authorized Apply, obtain the root and prefix from the selected checkout. Read the registered scan-local file once with `workbench_db.open_scan_local_file` and match its SHA-256 against the recorded digest. Compare **all** its bytes with the in-place diff for the reviewed before and after contents, and confirm the actual target paths and Git settings meet the example's conditions before either Git command. Other patches use the existing stage's scope and verification requirements. If the worker cannot establish how to apply the reviewed changes safely in the selected mode, record `failed` before writing.
- **Verify**: Do not modify source. Apply the selected mode's verification gates above against the recorded patch. Record `verified` only when evidence establishes that the original vulnerable path is closed, legitimate behavior remains intact, and the required checks pass; preserve exact evidence and any commands run in the verification summary. Otherwise record `failed` and state the failing gate or proof gap. Do not close the finding.

If a stage fails, record `failed` with the failing step and error in `summary`. Include the setter's error when registration fails.

When a parent thread delegates a remediation stage, the worker owns that stage through its terminal stage record. The parent remains an orchestrator and must not duplicate the worker's edits or treat a chat response as completion.

## Outcome and Output Contract

Follow the caller's output schema when supplied. Otherwise, include in the final response:

- outcome: `fixed`, `no_change`, or `blocked`
- the concrete vulnerable path, security invariant, and legitimate behavior that had to remain
- the selected patch strategy and why it was the narrowest complete repository-native option, or the unresolved product decision when blocked
- files changed
- tests or validation artifacts added
- commands run and their pass, fail, or unknown results
- evidence that the original vulnerable path is closed, distinguishing source assessment from observed execution
- explicit statement of how legitimate behavior was shown to remain intact
- remaining uncertainty or skipped validation, if any

If using a scan artifact directory, resolve it using `scan-artifacts.md`, then write a visible report to the fix report path. If there is no existing scan directory, a final chat summary is sufficient unless the user asks for a file.

## Hard Rules

- Do not report `fixed` until every verification gate for the selected mode has passed. Omit a check required by that mode only when repository evidence shows it is irrelevant; an unavailable required check makes verification `blocked` and must be reported.
- In standard mode, do not rely only on code inspection when a focused test or reproducer is feasible.
- Do not broaden the patch into unrelated cleanup, sibling findings, or architectural redesign without evidence that the broader change is required for complete closure.
- Do not remove user changes or unrelated local modifications.
- Do not weaken authentication, authorization, tenant isolation, input validation, sandboxing, or logging to make tests pass.
- Do not hide proof gaps. If the environment blocks validation, say exactly which command or setup failed and what evidence is still missing.

## Verify-Only Mode

This section ports upstream's separate `verify-fix` skill. Its trigger: use only
when the user explicitly requests verification that a security fix remediates a
reported vulnerability. Do not invoke it automatically while implementing fixes,
reviewing ordinary code changes, or running tests. Do not use it for non-security
fixes, candidate finding validation, or full repository scans.

### When to Use

Use this section only for an explicit request to verify a security fix. A request
to implement a fix or run its tests does not by itself request it. For other
tasks, follow the user's requested workflow and response format.

### Objective

Determine whether each supplied security finding has been fixed in the current
checkout. Operate in standalone verification-only mode; do not create, modify, or
delete repository files, apply patches, commit changes, write artifacts, or modify
issue trackers.

### Assessment Method

Use `static-finding-assessment.md` to identify the original attacker-controlled
source, security control, sensitive sink, reachable path, trust boundary,
counterevidence, and proof gaps. If the caller already supplied that reference in
the prompt, use the supplied contents without reading it again.

Use `standard` verification unless the caller explicitly selects
`verificationMode: static`. In static mode, assess the current source and diff,
the original exploit path and plausible bypasses, and legitimate behavior through
callers and existing tests read as source. Do not install dependencies or run
builds, tests, reproducers, or the application, including when validation
instructions request them. Repository-reading tools remain available. State in
the evidence that this is a static assessment and runtime checks were not
performed; do not count them as passed or require them for this assessment.
Missing runtime tooling alone does not make the result inconclusive, but a
material gap in the source evidence does.

### Verification Workflow

1. Establish the original vulnerability, its preconditions, affected security
   boundary, and legitimate behavior that must continue to work.
2. Confirm the current checkout contains the affected component. Follow moved or
   refactored code rather than treating a missing file, removed line, or changed
   function name as proof of remediation.
3. Trace the original exploit path through the current implementation and check
   the nearest relevant control, equivalent paths, and plausible bypasses.
4. In standard mode, run the original reproducer, focused regression checks, or
   legitimate-behavior checks only when they can run without modifying the
   repository. Preserve exact static evidence when runtime checks are unavailable.
5. Return one result per supplied finding, in the requested order. Treat closed
   tickets, unrelated passing tests, and the absence of a new scan finding as
   insufficient proof.

### Result Contract

For interactive conversations, use readable Markdown unless the caller requests
another format. Give a verdict for each finding, explain the supporting evidence
with source references, and identify relevant checks and remaining proof gaps.

When the caller requests JSON or supplies an automated result contract, return
exactly one JSON object in this shape. Use the same verdicts and evidence
requirements in either format.

```json
{
  "results": [
    {
      "id": "finding-or-issue-id",
      "status": "fixed|still_vulnerable|inconclusive",
      "evidence": "specific current source, exploit, test, or proof-gap evidence"
    }
  ]
}
```

- Use `fixed` only when evidence proves the original security boundary is closed
  and legitimate behavior remains intact.
- Use `still_vulnerable` only when evidence proves the original vulnerable path
  remains reachable.
- Use `inconclusive` for a repository mismatch, missing original context,
  unavailable checks required by the selected mode, an unproven legitimate
  control, or another material proof gap.

Never infer a stronger verdict by weakening the read-only boundary, substituting a
different vulnerability, or hiding missing evidence.
