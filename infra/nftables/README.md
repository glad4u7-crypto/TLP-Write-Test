# APAA OCI network qualification artifacts

The `apaa-worker-egress.nft` file is a parameterized-by-edit template for a dedicated disposable worker network namespace. It contains no `flush ruleset` and MUST NOT be applied to the host namespace.

Before a future authorized integration test:
1. Create a disposable Linux network namespace / rootless OCI worker network with no external default gateway.
2. Substitute the proxy IP and TCP port from the validated `ProxyWorkerTopology`.
3. Apply this file only inside that disposable worker namespace.
4. Inspect the complete effective ruleset with `nft -j list ruleset` and pass the snapshot to `parse_nftables_egress`.
5. Prove direct TCP/443, TCP/53, UDP/53, UDP/443, arbitrary IPv4 and IPv6 all fail while TCP to the exact proxy endpoint succeeds.
6. Destroy the namespace and verify cleanup.

The template and parser are not an installer and do not prove live host enforcement. No commands are run by APAA at this checkpoint.
