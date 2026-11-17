# P74 / BCS-04 — Strict nftables JSON attestation

## Implemented foundation

- Added \`core/nftables_attestation.py\`, a read-only semantic parser for the live
  \`nft -j list table inet apaa\` response.
- Requires exactly one \`inet apaa\` table, exactly two base chains (\`input\`,
  \`output\`), exact hooks, and \`policy drop\` on both.
- Compares the complete ACCEPT rule multiset with the dual-stack policy emitted
  by \`NftablesFirewallProvisioner.render_ruleset\`: loopback, tightly scoped
  IPv6 neighbour discovery, and exact proxy IP/port established/new TCP rules.
- Rejects unconditional ACCEPT, extra interfaces/destinations, unexpected
  expressions, indirect rules, duplicate/extra chains and malformed/oversized
  JSON. Returns a SHA-256 digest of the exact raw observation.
- Unit tests include the exact expected dual-stack ruleset and adversarial
  policy expansion cases.

## Important boundary

This parser is a pure verifier. It does not install firewall rules, mutate host
networking, launch containers, create signing keys, or authorize browser work.
It is not yet connected to a signed host-attestor or production
\`IsolatedWorkerBackend\`. Do not synthesize attestation fields from the launch
request. The real-host Chromium qualification workflow remains a separate,
manual-only test on a disposable Linux runner.

## Remaining BCS-04 gates

1. Verify the parser against captured JSON from the real disposable host; adjust
   only for semantically equivalent nft JSON encodings while keeping unknown
   rules fail-closed.
2. Implement an independent Podman runtime observer for immutable container ID,
   PID/start-time, namespace inode, cgroup membership, security options and
   effective limits.
3. Bind observer results and the nftables digest into the existing signed
   host-attestation challenge/response with one-time challenge consumption,
   freshness and replay protection.
4. Implement and test the production isolated-worker backend against the
   authenticated Owner browser job contract; dispatch remains disabled.
5. Run real-host Chromium, direct TCP/DNS/UDP/QUIC, TLS, proxy-outage, crash,
   timeout, orphan and cleanup qualification on a disposable host. Physical
   Android VpnService qualification is a separate platform task and is not
   claimed by this Linux implementation.

No merge, deployment, public browsing, Auto-Run, payment, purchase, trading or
money movement is enabled by this checkpoint.
