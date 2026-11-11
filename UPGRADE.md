# Upgrading to a new upstream release

How to move this port to a newer [openai/codex-security](https://github.com/openai/codex-security)
release. Upstream ships often and rewrites freely; follow every step, in order.
Nothing here compiles anything: the runtime is stdlib Python, and the only
things run are the installer, the finalizer, and pytest.

The previous upgrades are the worked examples: `git log --grep 'Upgrade to upstream'`.

## 0. Measure the gap

```bash
git clone --filter=blob:none https://github.com/openai/codex-security.git /tmp/up
cd /tmp/up
OLD=$(sed -n 's/^PINNED_SHA="\(.*\)"/\1/p' <port>/scripts/install.sh)
NEW=npm-vX.Y.Z                      # newest npm-v* release tag
P=plugins/codex-security
git log --oneline $OLD..$NEW -- $P | wc -l
git diff --stat $OLD $NEW -- $P/scripts $P/schemas $P/references $P/examples $P/shared $P/skills
git diff $OLD $NEW -- $P/skills $P/references | grep '^diff' # new and removed skills/references
```

If `$P` moved, the installer warns and finds the new location; update
`SRC_SUBDIR` in `scripts/install.sh`.

## 1. Review upstream line by line

Read every commit in `$OLD..$NEW -- $P`, not the titles. Flag and record in the
commit message anything that:

- adds a network call, telemetry, or a licence or account check to vendored code
  (`git grep -nE 'urllib\.request|http\.client|socket|urlopen|subprocess' $NEW -- $P/scripts`);
- moves code the port invokes into the TypeScript MCP app (`mcp-app/src/helpers/`);
- changes the canonical scan contract (schemas, `scan-contract.md`, example bundles);
- deletes a script that `SKILL.md` or `references/` invokes.

Deleted invoked scripts, which this step must catch:

```bash
grep -rhoE '\$CXSEC_HOME/[A-Za-z0-9_./-]+\.(py|json|md)' SKILL.md references | sort -u |
while read p; do r=${p#\$CXSEC_HOME/}
  git -C /tmp/up cat-file -e $NEW:$P/$r 2>/dev/null || [ -e assets/local-additions/$r ] || echo "MISSING $r"
done
```

## 2. Re-vendor the runtime

1. Set `PINNED_VERSION` and `PINNED_SHA` (the full SHA of the `$NEW` tag) in
   `scripts/install.sh`.
2. Install into a scratch home and read every `[fail]`/`[warn]`:
   `bash scripts/install.sh --force --home /tmp/cx`.
3. If the SARIF rebrand patch no longer applies, regenerate
   `assets/0001-rebrand-sarif-output.patch` against the new
   `finalize_scan_contract.py`, update `PATCH_SITES`, and copy the patch to
   `runtime/patches/`. The four sites are listed in `runtime/patches/README.md`.
4. If upstream added an offline skill subtree a mode needs (stdlib script plus
   assets), append it to `VENDOR_DIRS`. Never vendor `mcp-app/`, `agents/`, or
   upstream `SKILL.md` files.
5. Refresh `runtime/` from the scratch install, keeping `runtime/README.md` and
   `runtime/patches/README.md`:

   ```bash
   for d in scripts schemas references examples shared skills; do rm -rf runtime/$d; done
   (cd /tmp/cx && tar --exclude=__pycache__ -cf - scripts schemas references examples shared skills \
       LICENSE PROVENANCE.md patches/0001-rebrand-sarif-output.patch) | tar -xf - -C runtime
   ```

## 3. Carried helpers

Upstream keeps moving stdlib Python helpers into its TypeScript launcher
(`launch_codex_security_mcp --helper <name>`), which this port does not vendor.
For every helper a mode invokes:

- **Newly deleted upstream:** start from its last upstream Python
  (`git show $OLD:$P/scripts/<name>.py`), port every behaviour change the TypeScript
  helper made since, keep the existing CLI byte-compatible (additions only), and
  add it under `assets/local-additions/` at its runtime-relative path.
- **Already carried:** diff the matching `mcp-app/src/helpers/*.ts` over
  `$OLD..$NEW` and port each behaviour change.
- **Tests:** port the matching upstream TypeScript suites
  (`sdk/typescript/tests-ts/*.test.ts`, `mcp-app/tests/test_*.ts`) to pytest under
  `tests/`. Skip only Windows-launcher-specific cases and say which.
- Add each new helper to `check_scripts` in the installer, and to the
  local-additions tables in `runtime/patches/README.md`, `PROVENANCE` (the
  `write_provenance` heredoc in the installer), and `NOTICE`.

## 4. Port the doctrine

Each file in `references/` maps to one upstream file (the mode files to
`skills/<name>/SKILL.md`, `hard-rules.md` to `references/scan-prologue.md`; see
NOTICE). For each, three-way merge upstream's change into our adapted text:

```bash
git -C /tmp/up show $OLD:$P/<upstream> > base.md
git -C /tmp/up show $NEW:$P/<upstream> > theirs.md
git merge-file -p references/<ours>.md base.md theirs.md > merged.md
```

- Resolve conflicts toward upstream's meaning. When upstream rewrote a file
  rather than edited it, take its new text and re-apply the adaptations below.
- Adaptations, always: frontmatter becomes an HTML `when-to-use` comment; paths
  flatten into `references/` or `$CXSEC_HOME/...`; product branding goes; Codex
  app links become "a connected MCP server exposing ..."; Codex workers become
  `Agent` subagents; every MCP tool becomes a file operation listed in
  `references/workbench-file-protocol.md` (add a row for each new tool);
  `artifact-storage.md`'s save/read tools become direct writes under `<scan_dir>`
  or the target's `security_scans_dir`.
- New upstream skills: port as new modes when they work without the MCP server,
  the `codex-security` CLI, or Codex Security Cloud. Add a row to the `SKILL.md`
  table and a disambiguation line. Anything not ported goes under "Not included"
  in NOTICE.
- Prove contract changes: author a draft exactly as the docs now instruct,
  finalize it, and re-validate it:

  ```bash
  python3 $CXSEC_HOME/scripts/finalize_scan_contract.py --scan-dir <draft> --source-root <draft>
  python3 $CXSEC_HOME/scripts/validate_scan_contract.py --scan-dir <draft>
  ```

## 5. Update the records

- `NOTICE`: upstream release and commit, every new adaptation, the "Not
  included" list.
- `README.md`, `runtime/README.md` (add an "Upstream X.Y.Z changes" section),
  `runtime/patches/README.md`, `references/install.md`.
- `SKILL.md`: the frontmatter `description` must stay at or under 1024
  characters; check it after adding modes.

## 6. Verify

All of these must pass before committing:

```bash
bash -n scripts/install.sh
python3 -m py_compile assets/local-additions/scripts/*.py
bash scripts/install.sh --force --home /tmp/cx        # every check ok, smoke + legacy
CXSEC_HOME=/tmp/cx python3 -m pytest tests/ -q
bash scripts/install.sh --local --force --home /tmp/cx-local   # offline path from runtime/
grep -rn 'Codex\|codex_security_\|\.\./' references SKILL.md   # review each hit
```

Then reinstall the real runtime (`bash scripts/install.sh --force`) and the skill
copy, and run one real scan of a small vulnerable target end to end.

## 7. Commit

One commit, `Upgrade to upstream codex-security X.Y.Z`. The body names the
version range and commits, what upstream changed that mattered, every helper
newly carried, and anything deliberately not ported.
