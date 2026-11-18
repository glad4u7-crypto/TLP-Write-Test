# APAA P74 — Owner-requested disposable OCI qualification

Date: 2026-11-18

## Authorization and scope

The Owner requested completion of APAA S09-C01 / P74. This commit opts in to the repository's existing disposable-host real-worker qualification workflow.

The workflow must use only its built-in controlled read-only test:
- URL: https://example.com/
- Allowed origin: https://example.com
- Expected marker: Example Domain

## Safety boundary

- The runner is ephemeral GitHub-hosted Ubuntu; any cgroup, namespace, nftables and OCI changes are confined to that disposable runner and discarded with it.
- Use the existing rootless/non-root worker, seccomp, read-only root filesystem, namespace, cgroup and default-DROP egress policy unchanged.
- No user browser profile, credentials, cookies, personal websites, state-changing website actions, payments, purchases, trading or money movement.
- Do not weaken sandboxing, add host networking, add broad capabilities/seccomp allowances, pass host FDs, or enable direct network fallback.
- Preserve bounded sanitized evidence and cleanup results, including failure evidence.
- A successful workflow is evidence for this disposable-host test only, not Android or production acceptance.

## Current known evidence

- P93 pinned-source patch applicability and parser workflow: PASS, run 44221301621.
- APAA Security CI exact-head run: PASS, run 44221301304.
- These results do not establish a compiled diagnostic Chromium binary, Debian source-package equivalence, real OCI success, root cause, or a behavioral fix.

## Completion rule

Keep Browser/Worker dispatch disabled and Auto-Run OFF. P74 / S09-C01 remains NO-GO until the real-host evidence is inspected, the exact FD failure is understood and corrected (if reproducible), and all required security and Android acceptance gates are satisfied.
