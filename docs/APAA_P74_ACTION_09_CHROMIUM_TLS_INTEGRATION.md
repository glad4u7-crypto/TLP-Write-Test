# APAA P74 Action 09 — Chromium TLS Integration

**Status:** Test implementation committed; real Chromium CI execution pending.
**Checkpoint:** `APAA-P74-ACTION-09-CHROMIUM-TLS-INTEGRATION`
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`

## Acceptance boundary

These are three independent browser-process tests. Each starts Playwright's Chromium executable in headless mode and navigates through a constrained local CONNECT proxy to a local TLS fixture. Python `ssl` is used only to host the fixture; it is not the client under test. The assertions are based on Chromium navigation results and Chromium network error codes.

| Test | Certificate setup | Expected Chromium result |
|---|---|---|
| `test_chromium_accepts_certificate_signed_by_trusted_test_ca` | Leaf certificate signed by a private test CA installed into an isolated NSS database | Navigation succeeds; HTTP 200 |
| `test_chromium_rejects_trusted_certificate_with_hostname_mismatch` | Trusted CA, leaf SAN is `localhost`, URL host is `wrong.test` | `ERR_CERT_COMMON_NAME_INVALID` |
| `test_chromium_rejects_expired_certificate_signed_by_trusted_test_ca` | Trusted CA, expired leaf certificate with matching `localhost` SAN | `ERR_CERT_DATE_INVALID` |

## Trust-store handling

- The tests create a temporary HOME and isolated Chromium profile for each case.
- The test root is installed into the temporary NSS database with `certutil` and trust flag `C,,`.
- The browser context explicitly uses `ignore_https_errors=False`.
- No `--ignore-certificate-errors` or equivalent bypass is permitted.
- The proxy accepts CONNECT only for the local fixture hostname aliases and exact fixture port; all other destinations are rejected.
- CI installs `libnss3-tools` to provide `certutil`, then installs the pinned project dependencies and Playwright Chromium.

## Verification state

- [x] Three distinct Chromium navigation tests authored.
- [x] Trusted CA installed only into an isolated test trust database.
- [x] Hostname mismatch and expired-certificate cases use a CA-trusted leaf, so each test isolates the intended validation failure.
- [x] CI setup includes NSS certificate-store tooling.
- [x] CI exposes the three Chromium acceptance cases as separate named steps.
- [x] CI no longer cancels an active run merely because another commit is pushed to the same ref.
- [ ] Latest GitHub Actions run completes with all three tests passing.
- [ ] Review CI logs to confirm the browser process actually launched and the expected Chromium error codes were observed.

The workflow runs each Chromium acceptance test independently, then runs the remaining security suite while excluding only this dedicated three-test file. This makes the three browser outcomes individually visible in CI. Concurrency is configured to queue rather than cancel an active run for the same ref.

A test is not accepted merely because it was committed or because Python TLS tests pass. The acceptance state remains pending until GitHub Actions executes these tests successfully on this branch.

## Safety state

The tests use only local loopback TLS fixtures and a constrained local proxy. The production browser remains behind the signed runtime/firewall gate. This action does not enable public-web browsing, user login, form submission, downloads, purchases, payments, trading, money movement, paid services, Auto-Run, deployment, or firewall changes.
