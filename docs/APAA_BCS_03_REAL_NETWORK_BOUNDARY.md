# BCS-03 — Real Network Boundary

## Status
Pinned-IP TCP and mandatory HTTPS proxy CONNECT primitives are implemented as a
fail-closed foundation. This is NOT production network isolation; browser dispatch
remains disabled.

## Implemented
- The existing pinned connector dials numeric IPs and verifies the socket peer.
- A mandatory pinned HTTPS proxy is used; no direct-origin fallback exists.
- Proxy TLS validates CA and hostname and uses the proxy hostname for SNI.
- CONNECT contains the pinned numeric origin IP, not the origin hostname.
- Origin TLS uses the original hostname for SNI and certificate verification.
- Proxy refusal, malformed response, TLS failure and socket errors close all
  sockets and fail closed. Unit tests cover these cases.

## Critical qualification still required
A Python connector cannot prevent Chromium, DNS libraries, native extensions,
WebRTC, UDP/QUIC or unrelated processes from opening their own sockets.
Playwright routing is not an OS firewall.

Before live browser dispatch:
1. Force browser traffic through a trusted local proxy service.
2. Install default-deny host egress rules before browser launch; block direct TCP,
   UDP, DNS, DoT, DoH and QUIC, allowing only the local proxy path.
3. Implement and physically qualify Android VpnService/per-app enforcement.
4. Resolve once, reject the complete A/AAAA answer set if any address is
   non-global, pin the selected IP and CONNECT only to its numeric authority.
5. Revalidate each redirect as a fresh authorization transaction.
6. Keep CA and hostname verification mandatory; never use CERT_NONE or disable
   hostname checks.
7. On proxy startup, health, CONNECT or TLS failure, terminate the job and keep
   firewall egress closed.
8. Run real adversarial DNS-rebinding, mixed A/AAAA, IPv4-mapped IPv6,
   alternate-IP-encoding, SSRF metadata/loopback, redirect, proxy outage/bypass,
   direct TCP/DNS/UDP/QUIC and WebRTC tests. Verify with packet captures and
   firewall counters.

## Explicitly not enabled
No app.py/BrowserControlBoundary integration, Android VPN, nftables/iptables,
namespace/container enforcement, live browser traffic or Auto-Run. No payment,
purchase, trading, money movement or public exposure.

## Acceptance
BCS-03 is not production-complete until OS and Android enforcement, real-browser
adversarial tests, independent review and physical-device qualification pass.
Browser dispatch must remain disabled until then.
