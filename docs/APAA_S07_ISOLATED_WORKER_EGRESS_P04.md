# APAA S07 — P04 Isolated Browser Worker and Network Egress Security

**Checkpoint:** APAA-S07-C01-P04  
**Disposition:** OFFLINE SECURITY POLICY + VERIFICATION HARNESS ONLY  
**Branch:** `feature/approval-ui-e2e-p06`  
**PR:** #5 — keep Open + Draft; do not merge or deploy  
**Browser runtime:** NOT INSTALLED / NOT STARTED  
**Network proxy / firewall:** NOT DEPLOYED

## 1. Goal

P04 turns the P02 isolation topology and P03 URL/SSRF policy into machine-checkable offline contracts. It does not claim that a Python validator can create an OS sandbox or enforce network egress. A future deployment adapter must translate the validated profile into container/runtime/network controls and independently inspect the effective state before it can start a worker.

## 2. New implementation

### `core/browser_isolation.py`

A closed-schema validator for a future worker launch profile. It requires:
- non-root UID/GID;
- privileged mode, host network, host PID and host IPC disabled;
- read-only root filesystem and no-new-privileges;
- all Linux capabilities dropped;
- no host mounts and no secret mounts;
- only unique ephemeral writable paths below `/tmp/`;
- no persistent browser profile and no exposed CDP/devtools endpoint;
- direct egress disabled, proxy-only egress enabled, and DNS via proxy only;
- an explicit named internal proxy endpoint;
- bounded memory, CPU, PID count and job timeout.

Unknown/missing fields and unsafe values fail closed. The returned dataclass is immutable.

### `core/browser_egress.py`

A pure connection-decision helper for a future trusted egress proxy. The proxy supplies the DNS answer set it just resolved; the policy checks exact approved HTTPS origin, port 443 only, and every returned address using P03's public-unicast checks. It returns the hostname for TLS SNI and the exact normalized IP addresses that the proxy must pin for the connection.

No resolver is invoked by this helper. It opens no sockets and does not run a proxy server. The proxy implementation must use the returned pinned addresses for the actual socket connection; it must never resolve the hostname again between validation and connect.

### `tests/test_browser_isolation.py`

Offline regression fixtures cover secure/unsafe launch profiles, privilege and host namespace escapes, capability retention, host/secret mounts, writable path restrictions, proxy endpoint validation, resource caps, origin/port checks, private/mixed DNS answer rejection, empty answer sets and no implicit DNS/socket activity.

## 3. Required deployment topology (not deployed in P04)

```text
Trusted Streamlit Controller
       |
       | typed, bounded, one-time approved job
       v
Trusted Job Broker / Audit Store
       |
       | no approval signing key or tenant DB passed through
       v
Unprivileged Ephemeral Browser Worker
       |
       | ONLY allowed network destination:
       | fixed egress-proxy address:3128
       v
Policy-Enforcing Egress Proxy
       |
       | trusted-side DNS resolution
       | exact origin + TCP/443 + public-unicast IP validation
       | pin validated IP for actual connection
       v
Approved Public HTTPS Origin
```

The worker must have no route to the public internet, LAN, host gateway, metadata service or arbitrary DNS resolver. Container network policy / host firewall must deny all worker egress except the proxy's fixed address and port. DNS must be performed by the proxy on its trusted side, not by the worker. Disable UDP/QUIC and all non-proxy browser networking paths.

## 4. Egress proxy enforcement requirements

The future proxy adapter must, for every new destination connection:
1. Accept only HTTPS CONNECT requests and TCP port 443 in the initial read-only tier.
2. Parse and canonicalize the target; reject userinfo, malformed names, IP literals where not explicitly allowed, and non-HTTPS protocols.
3. Match scheme + canonical hostname + effective port against the exact per-job allowlist. Never use wildcard, suffix or substring matching.
4. Resolve DNS on the proxy side. Reject empty, malformed, private, loopback, link-local, reserved, multicast, unspecified or otherwise non-public answer sets. Reject mixed public/private answers.
5. Select only from the validated answer set and pin that exact IP to the socket connect. Do not perform a second hostname lookup at connect time.
6. Preserve the approved hostname as TLS SNI and validate the upstream certificate normally. Do not disable certificate validation or install a TLS interception CA.
7. Re-run policy for every new origin/connection and every redirect-induced new connection. A changed hostname, port or job allowlist invalidates the prior decision.
8. Fail closed on DNS timeout, proxy error, policy error, certificate error, address-family mismatch, connection retry to an unvalidated IP or unavailable audit.
9. Log only bounded metadata (job ID, normalized origin, decision, pinned IP, timestamp, reason code); never log page content, credentials, cookies, authorization headers or query secrets.
10. Prevent proxy bypass with firewall enforcement; application proxy settings alone are insufficient.

**HTTPS CONNECT limitation:** a conventional non-intercepting CONNECT proxy sees the hostname/port, not encrypted URL paths or HTTP redirect headers. Exact-origin policy is enforceable at CONNECT time; path-level allowlists and redirect-by-redirect URL inspection need a trusted browser-side request policy as a second layer. The proxy remains the network boundary and must still re-check each new connection. Do not add TLS interception in this project.

## 5. Worker isolation requirements

A future runtime adapter must apply and then inspect the effective settings, not merely trust a config file:
- dedicated unprivileged UID/GID; no privileged container;
- read-only root; bounded tmpfs only; no host path or secret mounts;
- no-new-privileges and drop all Linux capabilities;
- no host network/PID/IPC namespaces; no Docker socket, host daemon API or container runtime socket;
- seccomp/AppArmor/SELinux profile selected and tested for the target OS;
- cgroup CPU, memory and PID limits; wall-clock timeout and kill-on-cancel;
- no inherited environment secrets, tenant database, signing keys, browser profile, credential store or home directory;
- one fresh browser context per job; close context/process and destroy ephemeral storage on success, denial, timeout, cancellation or failure;
- no remote debugging/CDP listener, downloads, uploads, clipboard, shell or filesystem API;
- verify worker identity, mounts, namespaces, capabilities, routes and firewall rules at runtime before accepting a job.

A subprocess or Docker container alone is not proof of hostile-code isolation. Production deployment requires an OS/container security review and independent verification on the actual host.

## 6. P04 offline tests versus operational proof

| Control | P04 evidence | Operational proof still required |
|---|---|---|
| Worker profile schema | Offline validator + negative fixtures | Adapter applies settings and runtime attestation |
| Non-root / no capabilities | Manifest requires non-root + drop ALL | Inspect effective UID/GID and capability set |
| Host isolation | Manifest rejects host namespaces and mounts | Inspect namespaces, mounts and runtime socket access |
| Read-only filesystem | Manifest requires read-only root | Attempt writes on deployed worker; verify only bounded tmpfs |
| Resource limits | Bounded config values | Inspect cgroup limits and kill behavior |
| Proxy-only egress | Manifest requires proxy-only, no direct egress | Firewall test proving all bypass paths fail |
| Connection-time SSRF | Injected DNS-answer set checked offline | Proxy pins validated IP and cannot re-resolve to a different address |
| DNS leak prevention | Manifest requires DNS-via-proxy | Packet capture / firewall test proves worker cannot reach DNS |
| TLS | SNI field preserved in decision | Certificate validation and TLS tests on deployed proxy |
| Redirect behavior | P03 redirect URL policy tests | Browser request layer and proxy integration tests |
| Browser runtime | Not installed or started | Separate browser runtime authorization + security review |

## 7. Prohibited scope retained

- No browser runtime, Playwright package, Chromium binary, worker process or proxy service is added.
- No live DNS, HTTP, socket, packet, firewall or container operation is performed.
- No ExecutionGateway browser handler is registered.
- No shell, ADB, arbitrary filesystem, host-control, credentials, cookies, tokens, CDP or existing browser profile access.
- No payment, purchase, checkout, trading, investment order or money movement.
- Free-only by default; no paid API/provider, API key or billable service.
- Auto-Run OFF; Ask First remains the default.
- PR #5 stays Open + Draft + unmerged. No merge or deployment.

## 8. P04 exit gate

P04 is complete only when the offline validators/tests and both existing CI workflows pass on the exact final verification-record commit. That closes the policy/harness package only. A later, separately authorized deployment checkpoint must implement the worker and proxy adapters, prove the network boundary on the target host, perform independent security review, and retain browser execution disabled until all operational tests pass.
