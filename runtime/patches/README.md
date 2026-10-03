# Local patches to the vendored runtime

These are deliberate local changes to upstream code. **Re-vendoring from
openai/codex-security overwrites them** — re-apply every patch here afterwards
and re-run the verification below.

## 0001-rebrand-sarif-output.patch

Renames the five SARIF branding sites in `scripts/finalize_scan_contract.py` so
generated SARIF is attributed to this port rather than to Codex Security. These
values are cosmetic: nothing in the codebase reads them back, and neither
`validate_scan_contract.py` nor the report projection checks them.

| SARIF field | Upstream | Here |
|---|---|---|
| `tool.driver.name` | `Codex Security` | `cxsec-security` |
| `partialFingerprints` key | `codexSecurity/v1` | `cxsec/v1` |
| `run.properties.*SchemaVersion` | `codexSecuritySchemaVersion` | `cxsecSchemaVersion` |
| `run.properties.*TargetKind` | `codexSecurityTargetKind` | `cxsecTargetKind` |
| `run.properties.*CoverageCompleteness` | `codexSecurityCoverageCompleteness` | `cxsecCoverageCompleteness` |

`tool.driver.name` and the `partialFingerprints` namespace are what GitHub code
scanning uses to correlate alerts across uploads. Changing them re-baselines
alerts once. This rename was applied before any SARIF upload, so nothing was
orphaned — do not change them again casually.

### Apply

```bash
cd ~/.claude/codex-security && patch -p1 < patches/0001-rebrand-sarif-output.patch
```

### Verify

```bash
cd ~/.claude/codex-security
grep -c 'codexSecurity\|"Codex Security"' scripts/finalize_scan_contract.py   # must be 0
grep -c 'cxsec' scripts/finalize_scan_contract.py                            # must be 5
```

## Local additions

Files this port carries that upstream has since deleted. They live under
`assets/local-additions/` in the skill repo, mirrored by path, and the installer
copies them into `$CXSEC_HOME` after vendoring (so a `--force` re-vendor, which
wipes `scripts/`, never loses them).

### scripts/resolve_security_md.py

The offline SECURITY.md policy resolver. Upstream ported it to TypeScript inside
the MCP app in 0.1.28 (invoked as `launch_codex_security_mcp --helper
resolve-security-md`) and deleted the standalone Python helper. This port does
**not** vendor the MCP app — it is the offline, stdlib-only half — so the Python
resolver is kept as a local addition. Mode 7 (`mode-policy.md`), `mode-repo-scan.md`,
`core-scan.md`, and `security-guidance.md` all invoke
`$CXSEC_HOME/scripts/resolve_security_md.py` directly.

It is self-contained stdlib (`argparse`, `json`, `os`, `stat`, `sys`, `pathlib` —
no intra-plugin imports) and byte-identical across 0.1.24–0.1.26, its last upstream
revisions. The upstream 0.1.32 `security-guidance.md` states the TS helper "retains
the former Python helper's option abbreviations, help parsing, home expansion, and
path resolution" with the same root-to-leaf concatenation semantics, so the carried
helper matches current upstream behaviour.

Verify:

```bash
test -f "$CXSEC_HOME/scripts/resolve_security_md.py" && \
  python3 "$CXSEC_HOME/scripts/resolve_security_md.py" --help >/dev/null && echo ok
```

## Deliberately NOT patched

The canonical `documentType` literals (`codex-security.scan-manifest`,
`codex-security.findings`, `codex-security.coverage`), the fingerprint algorithm
`codex-security/v1`, and the snapshot-digest prefix `codex-security-snapshot/v1`
are **left alone on purpose**:

- No skill author ever types them. The finalizer stamps `documentType` and the
  finding identities onto an unsealed draft itself — verified by stripping them and
  finalizing successfully.
- `references/mode-triage.md` documents ingesting an existing
  `codex-security.findings` JSON artifact as a compatibility input. Renaming the
  literal would break that.
- Changing them means editing 3 JSON schemas plus ~8 sites in the finalizer, for
  zero user-visible difference.

`scan.producer` is author-supplied, not validated against any brand, and this port
already emits `{"name": "cxsec-security", ...}`. Nothing to patch.
