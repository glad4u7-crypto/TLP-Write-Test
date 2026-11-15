# APAA-S09-C01-P05 — Network Egress Authorization Contract

**Status:** Policy contract and focused tests committed; no live egress gateway implemented.  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`

## Files

- `core/egress_policy.py`: creates an immutable `EgressTarget` containing normalized hostname, port, scheme and the exact public IP address set resolved once during authorization.
- `tests/test_egress_policy.py`: covers single-resolution behavior, private/mixed DNS answers, unsafe URL rejection, explicit HTTP opt-in, IP-literal allowlisting and connector-result pin-set checking.

## Intended production connector contract

A separately implemented trusted egress connector must:

1. Accept only an `EgressTarget`; it must not resolve the hostname independently.
2. Connect to one of `pinned_addresses` directly, never to a fresh hostname resolution.
3. Preserve `hostname` for TLS SNI and certificate hostname verification.
4. Verify the actual connected peer IP is in the pin set.
5. Apply the same authorization to every redirect, subresource and protocol upgrade.
6. Deny unhandled protocols and fail closed on resolver, connector, TLS or policy errors.
7. Enforce process/network egress outside the browser so browser background traffic cannot bypass page routing.

## Explicit limitations

- This commit is an authorization data contract, not an HTTP CONNECT proxy, socket dialer, firewall or OS network sandbox.
- `validate_connector_result` can check a connector's reported peer address, but cannot prove that a connector actually used that address. Independent transport-level tests and trusted connector implementation are still required.
- DNS rebinding is not considered solved until the production connector uses the exact authorized IP and verifies the connected peer while preserving TLS hostname verification.
- No DNS/network requests are made by tests when the resolver is injected.
- No live websites, proxy settings, firewall rules, device permissions, deployments, payments, purchases, paid APIs or Auto-Run were used or changed.

## Verification

- Focused tests authored; execution result not available from the repository workflow lookup.
- Exact-head CI remains pending.
- P05 is an implementation milestone, not security approval.
