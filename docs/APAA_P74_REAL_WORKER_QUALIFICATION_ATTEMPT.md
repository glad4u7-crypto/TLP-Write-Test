# APAA P74 real-worker qualification attempt

This marker commit requests the repository's gated disposable-host qualification workflow.

- Target: GitHub-hosted `ubuntu-24.04` ephemeral runner only.
- Test destination: reserved public HTTPS fixture `https://example.com/` with marker `Example Domain`.
- Intended evidence: OCI runtime, dedicated network namespace, dual-stack proxy-only egress, nftables default-DROP, seccomp, cgroup limits, Chromium browser result, sanitized evidence artifact.
- No production host is targeted. No credentials, cookies, owner data, or secrets are included.
- A workflow failure is a qualification failure/pending result, not a reason to enable Browser/Worker dispatch.
