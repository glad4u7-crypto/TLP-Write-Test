# APAA S09 C01 P30 — Strict evidence JSON parsing

**Status:** repository implementation added; exact-head CI verification pending  
**Scope:** harden P29's read-only evidence privacy preflight against ambiguous or pathological JSON input.

## Threat addressed

Python's default JSON decoder silently accepts duplicate object keys and retains only the last value. An earlier sensitive field can therefore be hidden by a later duplicate key before the privacy walker sees the parsed object. The default decoder also accepts non-standard NaN/Infinity constants, and deeply nested input can raise RecursionError.

## Implementation

- Reject duplicate keys at every object depth using an object-pairs hook.
- Reject non-standard JSON constants (NaN, Infinity, -Infinity).
- Convert excessive parser nesting and malformed UTF-8/JSON into a fail-closed privacy-check error.
- Preserve a generic, value-free CLI error surface; never echo evidence values.
- Keep the scan read-only and retain the existing exact ten-file inventory and 16 MiB per-file bound.

## Regression tests

- Duplicate key at the root object.
- Duplicate key in a nested object.
- Non-standard JSON constant.
- Excessive JSON nesting.
- Existing secret-pattern, symlink, inventory, and CLI exit-code tests remain in place.

## Assurance limits

This is parser hardening, not DLP and not proof that evidence contains no personal or sensitive information. Human review and restricted evidence storage remain mandatory. It does not collect host facts, provision trust, sign evidence, run containers, change firewall rules, enable workers, or grant qualification approval.

## Verification gate

Mark P30 repository implementation verified only after Agent Foundation CI and Python Demo CI pass on the exact resulting PR head. C01 remains OPEN until the separate real-host, key-custody, durable anti-rollback, sink-side egress and independent-review gates in P27 are completed.
