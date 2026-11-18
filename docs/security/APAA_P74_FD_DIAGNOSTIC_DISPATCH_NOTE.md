# APAA P74 — disposable-host FD diagnostic qualification trigger

This note records an opt-in request to execute the existing P74 real-worker qualification workflow on its disposable GitHub-hosted Ubuntu runner.

Safety boundary:
- The workflow uses only its built-in controlled test URL and marker defaults (https://example.com/; read-only Chromium DOM smoke).
- It runs inside the workflow's disposable OCI worker with the existing seccomp, cgroup-v2, rootless worker and default-deny egress setup.
- Host cgroup/nftables changes are confined to the ephemeral runner and are discarded with that runner.
- No user browser profile, credentials, cookies, personal website, payment, purchase, or state-changing site action is involved.
- This is diagnostic qualification only. A passing CI patch-validation workflow is not proof of real-host success.
- Any FD ownership failure must preserve the crash stderr, bounded sanitized procfs snapshot and stack evidence; do not weaken isolation or apply a speculative FD lifecycle fix.

The workflow is intentionally gated by the commit marker `[run-p74-real-worker]` on this feature branch. This commit is the explicit opt-in trigger for that disposable-host run.


## Follow-up run request — improved process attribution

A second disposable-host run is requested after the attribution correction: the last prefixed log PID is now recorded only as preceding-log context; the stack-matched process is kept separate; structured fatal-path FD instrumentation is explicitly marked absent when the runtime binary does not contain the diagnostic patch; and the per-snapshot evidence cap is 250 KB. Use only the same built-in `https://example.com/` read-only local Chromium smoke. Preserve the NO-GO result if the fatal marker reproduces.


## Third run request — exact-build symbolication

Run the same read-only `https://example.com/` disposable OCI qualification after adding the Debian debuginfod Build-ID lookup and `eu-addr2line` post-processing step. Preserve the FD ownership NO-GO if it reproduces; symbolication is best-effort and must not alter the worker image or isolation policy.
