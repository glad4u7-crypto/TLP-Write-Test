# APAA P74 real-worker qualification trigger

- Execution target: disposable GitHub-hosted Ubuntu 24.04 runner
- HTTPS test URL: https://example.com/
- Exact origin: https://example.com
- Expected HTML marker: Example Domain
- Scope: one isolated Chromium worker, dual-stack proxy path, direct-egress probes, cgroup/seccomp readback and host-veth packet capture
- Product Public Live Browsing: remains disabled
- Product worker dispatch: remains disabled
- No secrets, API keys, paid providers, payments or user data are supplied to this run

The qualification job is gated by the commit message marker
`[run-p74-real-worker]`. This record does not represent a PASS; only the
workflow evidence artifact and successful job result can establish that.
