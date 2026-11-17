# BCS-02 — Secure Browser Adapter

## Status

Implementation scaffold added on the APAA Personal Edition foundation branch.
This is not approval to enable browser execution. BCS-01 Owner approval remains
the only authorization boundary, and BrowserControlBoundary remains disabled.

## Implemented in this block

- A fresh non-persistent BrowserContext is created by PlaywrightBrowserLauncher.
  The context rejects downloads and blocks service workers.
- BrowserSession exposes its owned context and closes context, browser and
  Playwright manager deterministically.
- SafeNavigationController supports persistent BrowserContext-wide routing.
  The route validates the initial URL, the browser-reported redirect chain
  (including loop and hop limits), and every routed subresource for the full
  adapter session, not only during page.goto().
- SecureBrowserAdapter requires a trusted per-request egress guard. A request
  is continued only when the guard returns the literal boolean true.
- Only GET and HEAD are accepted. Request bodies and multipart requests are
  rejected. Download acceptance is disabled and file chooser selections are
  cleared on the initial page and every popup/new page in the context.
- WebSocket routing is mandatory; adapter startup fails closed if the runtime
  cannot install a WebSocket deny handler. Each WebSocket is closed with
  policy code 1008.
- Background/unsupported resource types (including media, eventsource,
  websocket and other) are denied by the default allowlist.
- Adapter cleanup removes persistent routing and closes the isolated session.

## Implementation audit corrections\n\n- Fixed the initial pytest collection error caused by using pytest reserved parameter name `request`.\n- Fixed persistent-route cleanup by retaining the exact bound callback object required by Playwright `unroute()`.\n- Enforced redirect-chain hop limits and loop detection using the browser-reported redirect ancestry on every routed request.\n- Applied file chooser rejection to popups and every new page in the BrowserContext, not only the first page.\n- Tightened the default resource allowlist: XHR, fetch, manifest, beacon/ping, media, EventSource, WebSocket and unknown resource types are denied unless a trusted caller explicitly changes the allowlist.\n\n## Critical security boundary — not yet qualified

Playwright routing is not an OS/network sandbox. It does not prove that browser
process traffic, DNS, UDP/QUIC, WebRTC, browser update checks, proxy bypasses or
other traffic outside Playwright routing is blocked.

The egress guard supplied to SecureBrowserAdapter must be backed by a trusted
local host adapter and an enforced default-deny network boundary that pins
connections to validated public IP addresses while preserving TLS SNI and
certificate verification. A boolean callback alone is not that boundary.

No production egress guard, Android host adapter, firewall/namespace proof,
real Chromium redirect/DNS-rebinding/WebSocket bypass qualification, or
physical Android qualification is included in this change. Do not pass a
placeholder guard in a live environment.

## Explicitly not enabled

- BrowserControlBoundary handler remains disabled.
- No Browser Job is dispatched to SecureBrowserAdapter from the app.
- Auto-Run remains OFF.
- Downloads, uploads, form submissions and WebSockets remain prohibited.
- No payment, purchase, trading, money movement, paid API or public exposure.

## Verification required

1. Run the complete Python suite, compilation and dependency audit.
2. Run exact-head CI and review the changed-file diff.
3. Add real-browser integration tests for redirects, subresources, file chooser,
   downloads, WebSocket attempts, service workers and background requests.
4. Prove network enforcement outside Playwright, including DNS rebinding,
   direct TCP/DNS/UDP/QUIC and proxy outage/bypass tests.
5. Complete physical Android qualification and independent security review
   before any browser dispatch enablement.

**Disposition:** BCS-02 policy adapter implementation is present; operational
browser execution remains DISABLED and security qualification is PENDING.
