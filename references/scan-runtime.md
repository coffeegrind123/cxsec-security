<!-- Ported from upstream references/scan-runtime.md (0.5.0+), which replaced the
     retired capability preflight (config-preflight.md, config_preflight.py,
     preflight/capability-profiles.toml). Read once by modes 1 and 2 before source
     review. Upstream's "Daybreak Access Advisory" section checks a ChatGPT account
     through a plugin MCP tool and has no equivalent here. -->

# Scan Runtime

Use the current tool surface for Standard and diff scan delegation. If the `Agent`
tool is deferred and a tool-search tool is available, load it once before deciding
that subagents are unavailable. Use only successful `Agent` calls and their
returned results as evidence that workers started. Any worker allowance the user
sets is a maximum, not a required number of workers.

When subagents are unavailable or a worker cannot start, continue the assigned
review yourself. Account for every authorized file and security question, and
report actual coverage gaps. Do not inspect or edit persistent harness
configuration to enable optional workers. Apply relevant `SECURITY.md` guidance
(`security-guidance.md`); the absence of optional tools does not block source
review.

For a Standard or diff scan, use the scan context you wrote to
`<scan_dir>/scan-context.json` as authoritative, and record the `threat_model`
phase in `<scan_dir>/progress.jsonl` before starting architecture mapping. You
still validate the target, scope, and the sandbox and permission limits of the
current session yourself. A deep scan (`mode-deep-scan.md`) owns its own round
setup and progress and does not depend on this file.
