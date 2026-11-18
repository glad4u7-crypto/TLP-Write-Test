# APAA P74 diagnostic qualification trigger

Owner-authorized disposable GitHub-hosted Ubuntu qualification using only the reserved public HTTPS fixture:
- URL: https://example.com/
- Allowed origin: https://example.com
- Expected marker: Example Domain

This run includes the bounded read-only Chromium FD/process snapshot collector and best-effort exact-build symbolication added to the worker script. It sends no credentials, cookies, personal data, or writes. The sandbox, seccomp, namespace, cgroup, and default-DROP network policies remain unchanged.

A failed run remains NO-GO; do not weaken isolation controls or enable Browser/Worker dispatch or Auto-Run.


## Second diagnostic attempt

This second attempt includes sanitized Chromium process-type classification for crashpad-handler and broker processes. It is intended to disambiguate the process owning the symbolicated FD-ownership stack; it does not alter Chromium behavior or sandbox settings.
