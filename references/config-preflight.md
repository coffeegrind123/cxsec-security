# Capability Preflight

Run the read-only preflight helper before substantive scan work. It evaluates the
routed capability profile from `$CXSEC_HOME/preflight/capability-profiles.toml`
and prints one JSON result.

Resolve `<python_command>` to the configured Python interpreter (`$PYTHON` when
one is provided), otherwise `python` on Windows and `python3` on Unix-like hosts.

## The invocation

Bare, the helper returns `status: "incomplete"` because it cannot see the runtime
by itself. Declare the capabilities honestly. This is the verified working form:

```bash
python3 $CXSEC_HOME/scripts/config_preflight.py \
  --profile <security_scan|security_diff_scan|deep_security_scan> \
  --cwd <scan-working-directory> \
  --runtime-check delegation_available=<true|false> \
  --runtime-check goal_tools_available=false \
  --multi-agent-runtime-owner native \
  --multi-agent-runtime-version v2 \
  --multi-agent-session-cap <observed concurrent subagent capacity> \
  --multi-agent-runtime-provenance tool-surface \
  --effective-config features.goals=true
```

You may also route by skill name with `--skill <security-scan|security-diff-scan|deep-security-scan>`
instead of `--profile`.

Determine the runtime-check values from the actual tool surface:

- **`delegation_available`** — `true` when a subagent/`Agent` tool is available.
  Delegation tools may be deferred rather than present in the initial tool list;
  search the deferred tool surface before passing `false`. Pass `false` only after
  discovery fails to expose a usable delegation tool.
- **`goal_tools_available`** — `false`. There are no goal tools here. This
  legitimately fails, but its severity is `suggest` in every profile, so it does
  not block. State the coverage objective in your first visible update instead.
- **`--multi-agent-session-cap`** — the observed number of subagents you can
  actually run concurrently, including the root. Profiles that evaluate worker
  capacity subtract the root thread. Do not inflate this; a slot count is the
  configured maximum, not a promise that every worker starts.

A passed `delegated_workers` check means the runtime supports delegated review and
the explicitly invoked scan authorizes it. If delegation is unavailable, pass
`delegation_available=false`, continue on the parent-only fallback, and do not
describe configured slots as running workers or claim reduced coverage that did
not happen.

If a profile checks skill dependencies, repeat `--available-plugin-skill <name>`
for the reference files present in this skill (for example `security-scan`). Use
what is actually available, not what exists on disk elsewhere.

Save the result to `<scan_dir>/preflight.json`.

## Config discovery

The helper discovers config itself from `--cwd`: it reads `/etc/codex/config.toml`,
then `$CODEX_HOME/config.toml` (default `~/.codex`), resolves
`project_root_markers`, checks the matching
`[projects."<absolute-project-root>"].trust_level`, and loads trusted project
`.codex/config.toml` layers from the project root down to `--cwd`. It does not
load project layers unless the user config marks that project root as `trusted`.

**None of those files need to exist.** When they are absent the helper applies the
documented defaults from the registry, which is the normal case here. Pass
`--effective-config <path>=<json-value>` for any value the runtime knows more
accurately than a config file does. Repeated `--config <path>` arguments override
automatic discovery entirely, lowest precedence first.

## Interpreting the result

Use the helper result as the preflight source of truth. Do not independently
reinterpret profile requirements or compare raw config text for equality.

Requirement severities:

- `block` — the requested workflow cannot be claimed honestly when unmet
- `warn` — the workflow can continue only on the documented degraded path
- `suggest` — the workflow can continue; mention the improvement when it
  materially affects long-running scan quality or resumability

Top-level `status` values:

- `ready` — continue, explaining any material warn or suggest limitation
- `incomplete` — a capability the profile needs is `unknown`. Establish it from
  the tool surface and rerun with an explicit `--runtime-check`. Never treat
  `incomplete` or an unknown value as evidence that a capability is available.
- `blocked` — handle remediation below
- `error` — report the exact blocker and retry the documented recovery when
  possible

Do not warn merely because a user's value differs from a suggested patch. Warn or
block only when the evaluated capability requirement is actually unmet.

When a requirement is config-backed, compare the effective resolved value when the
runtime exposes it; otherwise fall back to the loaded config value and the
documented default from the profile.

## Remediation

When the result includes remediation patches, present the concrete config delta
and **ask before editing persistent user configuration**. If the user approves,
edit only the helper's reported `user_config_path`; never infer
`~/.codex/config.toml` or another config home. Resolve a conflicting
higher-precedence project or profile value in the source the helper reports rather
than hiding it with a lower-precedence edit. Never rewrite config beyond the
helper's concrete patches.

Patches with `kind = "host_setting"` are host-level setup guidance, not edits to
persistent config. Present them as guidance.

If the user declines required remediation, ask whether to stop or leave the scan
directory for a later retry. Do not loop, and do not record the scan as failed
automatically.

For any non-ready result, do not fail automatically. If remediation is
unavailable, the helper cannot run, it returns an error envelope, or a rerun
remains blocked or incomplete, preserve `<scan_dir>` and retry or hand off while
recovery may still be possible. Record the scan as failed
(`<scan_dir>/scan-failed.md`) only after the documented recovery path is exhausted
and the blocker is confirmed unrecoverable, or when the user explicitly cancels.

## Where to run it

Run the helper in the parent so its exact command, exit code, and JSON result stay
observable. Never invent or reconstruct a helper result.

If you delegate preflight to a subagent instead, require a concrete subagent id
from a successful spawn, wait for that specific id, and accept a result only from
it. If spawning fails, run the helper in the parent and report the spawn failure.
A delegated preflight should return only a compact summary: the executed command
and exit code, overall status, unmet or unknown capabilities, the reported
`user_config_path`, and applicable remediation — plus the source path for any
conflicting setting. This keeps preflight inspection out of the primary scan
context.

Deep scan's repeated discovery rounds do not require a particular parent
delegation runtime, ownership, capacity, or depth beyond what the
`deep_security_scan` profile checks.
