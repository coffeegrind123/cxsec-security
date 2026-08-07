# Installing and verifying the runtime

`scripts/install.sh` vendors the runtime that every scan mode depends on, patches
it, and then proves it works. Read this file when a check fails, when you need to
re-vendor, or when the host has no network.

## Commands

```bash
bash scripts/install.sh                 # install if absent, otherwise verify
bash scripts/install.sh --check         # verify only: no network, no writes
bash scripts/install.sh --force         # re-vendor over an existing tree
bash scripts/install.sh --local         # install from the bundled runtime/ tree, offline
bash scripts/install.sh --home <dir>    # install somewhere other than $CXSEC_HOME
bash scripts/install.sh --ref <sha>     # vendor a ref other than the pinned one
bash scripts/install.sh --no-smoke      # skip the end-to-end finalizer test
```

Exit codes: `0` ok, `1` verification failed, `2` usage error, `3` missing
prerequisite, `4` fetch or extract failed, `5` patch failed.

The default run never re-downloads over a working install — it verifies instead.
Only `--force` overwrites, and it moves each replaced directory to
`<name>.bak.<UTC timestamp>` first. Delete stale `*.bak.*` directories by hand
once a new install verifies.

## What lands where

Into `$CXSEC_HOME` (default `~/.claude/codex-security`), from
`openai/codex-security` at the pinned commit, path
`sdk/typescript/_bundled_plugin`:

| Directory | Contents |
|---|---|
| `scripts/` | 34 stdlib-only Python helpers. No pip install, no network calls. |
| `schemas/` | 12 JSON Schemas for the scan contract. |
| `references/` | Upstream shared reference set. |
| `preflight/` | `capability-profiles.toml` — capability gate definitions. |
| `examples/` | `completed-scan/` — the fixture the smoke test finalizes. |

Plus `LICENSE` (Apache-2.0), a generated `PROVENANCE.md`, and `patches/` holding
the applied patch.

**`scripts/` and `schemas/` must stay siblings.** `finalize_scan_contract.py`
resolves schemas as `<script_parent>/../schemas`; moving either one breaks report
generation with a schema-resolution error, not an obvious layout error.

## What the checks mean

| Check | Proves |
|---|---|
| `python 3.x` | An interpreter 3.9+ exists. The runtime is stdlib-only, but it still needs one. |
| `scripts/ and schemas/ are siblings` | The load-bearing layout constraint holds. |
| `<script>.py runs` | Each load-bearing helper parses and starts under this interpreter. |
| `SARIF rebrand patch applied` | 0 upstream branding sites, 5 `cxsec` sites in the finalizer. |
| `capability preflight emits parseable JSON` | `config_preflight.py` can read its profile registry. |
| `end-to-end` | The bundled example scan, stripped back to an unsealed draft, finalizes into a sealed manifest, `report.md`, and SARIF 2.1.0 attributed to `cxsec-security`. |
| `report.md passes validate_report_format.py` | The generated report satisfies the format validator. |

The end-to-end check is the one that matters: it exercises schema resolution,
identity derivation, sealing, report generation, and SARIF export in one pass.

## When a check fails

- **`\$CXSEC_HOME does not exist`** — nothing is installed. Run `install.sh`.
- **`missing scripts/ or schemas/`**, **`not siblings`** — a partial or moved
  tree. Re-vendor with `--force`.
- **`<script>.py present but --help failed`** — truncated file or a broken
  interpreter. Check `python3 -V`, then `--force`.
- **`SARIF rebrand not applied`** — the finalizer is upstream-branded or was
  edited. `--force` re-vendors and re-applies. Generated SARIF is otherwise
  attributed to Codex Security, which re-baselines GitHub code-scanning alerts.
- **`finalizer failed on the example scan`** — the log is printed inline. A schema
  error here almost always means the sibling layout broke.
- **`patch failed against <ref>`** — upstream changed the SARIF emitter. Vendor
  the pinned ref instead, or regenerate `assets/0001-rebrand-sarif-output.patch`
  against the new source and re-run. Do not skip it silently.
- **`examples/completed-scan absent`** — an install predating the fixture. The
  end-to-end check is skipped, not failed; `--force` vendors it.

## No network

The runtime makes no network calls; only fetching needs one.

When the skill was installed from its git repository it ships a `runtime/` tree:
`install.sh --local` installs from that copy and never touches the network. A
default run also falls back to it automatically if the download fails. The bundled
tree is already patched, so the installer reports `already applied (source tree was
pre-patched)` rather than patching twice.

Otherwise, on an air-gapped host, copy a verified `$CXSEC_HOME` across whole, then
run `install.sh --check --home <dir>` to confirm it survived the trip. The check
path never touches the network.

`gh` is used for the fetch when available (authenticated, no rate limit), with a
`curl` fallback to `codeload.github.com`. Either is enough.

## Transports the installer cannot provide

Modes 1–3, 5–7 and 9 need nothing beyond the runtime. Modes 4 and 8 additionally
need a transport:

- **GitHub** — `gh` authenticated (`gh auth login`), or a connected MCP server
  exposing GitHub tools.
- **Linear**, **Jira** — a connected MCP server. There is no CLI fallback and no
  REST substitute; `mode-track.md` says to stop rather than switch transports.

The installer reports which of these are present. It cannot install MCP servers —
configure them in your MCP settings and re-check tool presence in-session.

## Deliberately not vendored

The upstream MCP server (`mcp/server.mjs`) and the Codex-CLI-driven
`deep-security-scan` worker fan-out. `workbench-file-protocol.md` is the
file-based replacement for every upstream MCP tool.
