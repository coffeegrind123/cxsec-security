# cxsec-security

A Claude Code [Agent Skill](https://agentskills.io) for application security
review: scan a repo or a diff for vulnerabilities, triage findings you already
have, fix and verify them, write them up, and file them — with CWE/CVSS-grounded
reporting and deterministic SARIF 2.1.0 output.

Ported from [openai/codex-security](https://github.com/openai/codex-security)
(Apache-2.0). See [NOTICE](NOTICE) for what changed.

## Install

Clone into your personal skills directory. The directory name must match the
skill name, so clone it as `cxsec-security`:

```bash
git clone https://github.com/coffeegrind123/cxsec-security.git \
  ~/.claude/skills/cxsec-security

bash ~/.claude/skills/cxsec-security/scripts/install.sh
```

The installer vendors the pinned upstream runtime into `$CXSEC_HOME` (default
`~/.claude/codex-security`), applies the SARIF-attribution patch, and then proves
the install by finalizing a bundled example scan end to end.

```bash
scripts/install.sh              # install if absent, otherwise verify
scripts/install.sh --check      # verify only: no network, no writes
scripts/install.sh --local      # install from the bundled runtime/ tree, offline
scripts/install.sh --force      # re-vendor from upstream
```

`runtime/` in this repo is a working copy of that tree, so `--local` gives you an
offline install. Read [`references/install.md`](references/install.md) when a
check fails or you need to re-vendor or pin a different upstream ref.

**Requirements:** `python3` 3.9+. Nothing else for scanning — the runtime is
stdlib-only and makes no network calls. Filing findings (mode 8) and GitHub
finding intake (mode 4) additionally need authenticated `gh`, or a connected MCP
server exposing GitHub, Linear, or Atlassian/Jira tools.

## The nine modes

`SKILL.md` is a router. It picks one mode, reads only that mode's reference file,
and follows it.

| # | Mode | Use when |
|---|---|---|
| 1 | Repository scan | Audit a whole repo or a scoped path. The default scan. |
| 2 | Diff scan | Review a change set: PR, commit, branch diff, working-tree patch. |
| 3 | Deep scan | Explicitly asked for deep, exhaustive, or multi-pass. |
| 4 | Triage | You already have findings — SARIF, CVE/GHSA, scanner tickets — and want repo-impact verdicts. |
| 5 | Fix | Fix *and verify* one identified finding. |
| 6 | Write-up | Turn findings and PoCs into a distributable disclosure report. |
| 7 | Policy | Author or review a repository `SECURITY.md`. |
| 8 | Track | File findings as Linear/Jira/GitHub issues or a draft GitHub advisory. |
| 9 | Harden | Structural change beyond per-finding patches, with tradeoffs and a migration plan. |

Modes 1–3 run four phases internally — threat model → discovery → validation →
attack path. Phase files are never entry points.

## How reports are produced

You author the canonical scan JSON as an *unsealed draft*, then finalize once:

```bash
python3 $CXSEC_HOME/scripts/finalize_scan_contract.py \
  --scan-dir <scan_dir> --source-root <repo_root>
```

The finalizer validates and seals it, derives finding identities and
fingerprints, and generates `report.md` plus SARIF 2.1.0. `report.md` and the
SARIF are never hand-written.

`scripts/` and `schemas/` must stay siblings inside `$CXSEC_HOME` — the finalizer
resolves schemas as `<script_parent>/../schemas`.

## Layout

```
SKILL.md                  router: mode selection, standing rules, reference map
references/               37 files, loaded on demand
  mode-*.md               the nine modes
  phase-*.md              the four scan phases
  workbench-file-protocol.md   file-based replacement for every upstream MCP tool
  install.md              installer reference and failure playbook
scripts/install.sh        install / verify / re-vendor the runtime
assets/                   the SARIF-attribution patch
runtime/                  vendored upstream runtime (stdlib Python + JSON Schemas)
```

## What is not ported

The upstream MCP server (`mcp/server.mjs`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out. `references/workbench-file-protocol.md` is
the authoritative mapping from every upstream MCP tool to its file-based
replacement, and it is required reading before any scan mode.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
