# APAA Personal Edition — P74 Browser Execution Security

## Scope

P74 adds the execution-boundary primitives between the existing offline browser
policy and a future independently attested worker adapter. Browser execution
must remain disabled unless that adapter is present and the runtime/firewall
attestation gate succeeds.

## Added implementation

- `core/browser_execution.py`
  - `PinnedDestination` accepts only explicit, normalized public unicast IPs.
  - `PinnedHTTPSConnection` dials the pinned IP, checks the connected peer,
    retains the original hostname for TLS SNI and certificate hostname checks,
    and uses the platform trust store with certificate verification required.
  - Redirects are not followed by this transport. Every redirect must be
    re-authorized and resolved to a fresh pin set by its caller.
  - `CancellationToken` provides cooperative cancellation.
  - The coordinator enforces a hard wall-clock deadline and requires worker termination to return explicit `True` only after OS process exit and ephemeral storage cleanup are confirmed. A timeout/cancel is never audited as closed when termination is unconfirmed.
  - The worker `run()` contract requires per-job browser context/profile teardown before returning.
  - Worker results are recursively restricted to JSON-safe values with string keys, finite JSON numbers, bounded nesting and the job's `max_response_bytes` limit.
  - `BrowserExecutionCoordinator.from_attested_runtime()` requires the concrete `AttestedBrowserRuntime` class, then launches through its signed runtime/firewall evidence verifier before accepting a production worker handle; duck-typed substitutes are rejected.
  - `BrowserExecutionCoordinator` requires a worker adapter, performs live
    DNS resolution for every hostname, validates every DNS answer, and passes
    the complete pin set to the worker.
  - Every run receives a fresh random session ID. The adapter must create a
    new non-persistent browser context/profile and destroy it at job end.
  - Audit writes are fail-closed. Records intentionally omit URLs, query
    strings, cookies, credentials, and page contents.
  - No local-process fallback is provided. Missing worker integration means
    browser execution remains disabled.

- `tests/test_browser_execution.py`
  - Covers TLS verification requirements, pinned IP validation, private/mixed
    DNS rejection, fail-closed worker configuration, audit failures, runtime
    result validation, cancellation, hard timeout termination and cleanup confirmation.

## Required production adapter contract

A production `BrowserWorker` is privileged code and must not be implemented
as a plain Playwright process on the application host. It must:

1. Start a dedicated container or VM worker with a pinned, reviewed image.
2. Apply user, PID, network, IPC, UTS and mount isolation; drop all Linux
   capabilities; use a read-only root filesystem, no-new-privileges and a
   reviewed seccomp profile.
3. Apply host-enforced default-deny egress before the browser starts. Permit
   only TCP to the explicitly configured egress proxy. Block direct DNS,
   UDP, QUIC, WebRTC/STUN, WebSockets that escape proxy policy, metadata
   services, loopback and private networks at the network boundary.
4. Configure the proxy to resolve destinations itself, validate every A/AAAA
   answer, reject mixed/private/special-use results, connect only to a selected
   pinned IP, and preserve the original hostname for TLS SNI and certificate
   verification. Revalidate every redirect and every new connection.
5. Keep TLS certificate-chain validation and hostname verification enabled.
   Never use an insecure TLS context or ignore certificate errors.
6. Create a unique ephemeral browser context/profile per job, disable
   downloads, uploads, service workers and persistent storage unless a later
   separately approved capability requires them. Do not expose CDP/debug ports.
7. Enforce a hard wall-clock deadline outside the browser process. On cancel
   or timeout, terminate the whole worker process/container (not just a page),
   wait for exit, and remove ephemeral storage.
8. Emit append-only, access-controlled audit events for accepted, started,
   cancelled, timed-out, failed and completed jobs, including worker/session
   identifiers and policy decision metadata but never secrets or page content.
9. Produce fresh signed runtime and host-firewall evidence. The control plane
   must verify it through `core.attested_browser_runtime` before allowing the
   worker to accept a job.

## Explicit non-claims

This checkpoint does not provide a container/VM runtime adapter, host firewall
rules, a live egress proxy, browser process supervision, a durable audit-store
backend, Android/Termux isolation, or end-to-end live browser execution.
The pinned HTTPS transport is a transport primitive, not proof that Chromium
traffic is forced through it. Network enforcement must be outside the browser
process. No live-site actions, payments, purchases, autonomous submissions,
or deployment are enabled.

## Verification

Automated tests are added but must pass on the exact resulting branch head.
Do not mark P74 complete until full Python CI and browser security smoke checks
pass, and the production adapter has passed independent container, firewall,
TLS, redirect and direct-egress-bypass verification. Physical Android testing remains excluded from this checkpoint unless
the user separately authorizes it. C01 must be completed and explicitly
approved before C02 starts.


## Current checkpoint record

- Latest implementation branch head: `20e9f3e311ea85adc888aace4c0004932a0bcd61`.
- New P74 regression tests authored: 20 in `test_browser_execution.py` and 15 in `test_attested_browser_runtime.py` (35 total).
- Exact-head GitHub combined status and PR workflow lookup returned no check results. Therefore automated PASS is **not verified**.
- No physical Android/device testing was performed.
- Browser execution remains disabled until a real isolated worker, host-enforced egress boundary, durable audit adapter, and successful exact-head CI/security verification exist.
