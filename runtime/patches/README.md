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
