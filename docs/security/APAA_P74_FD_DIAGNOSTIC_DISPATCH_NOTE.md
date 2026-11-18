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
