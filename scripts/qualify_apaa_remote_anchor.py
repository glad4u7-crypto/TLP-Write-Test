#!/usr/bin/env python3
"""Explicit write-test for an isolated external APAA anchor test record.

Requires a pre-provisioned test anchor at revision zero and explicit
--confirm-write-tests. It never targets the production owner anchor unless an
operator misconfigures the dedicated test ID; the ID prefix is enforced.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import sys

from core.offline_owner_recovery import AnchorState
from core.remote_owner_anchor import HTTPSMonotonicAnchor, RemoteAnchorError


def run_conformance(
    *, client_factory, test_anchor_id: str,
) -> dict[str, object]:
    if type(test_anchor_id) is not str or not test_anchor_id.startswith("apaa-test-"):
        raise RemoteAnchorError("Write qualification requires a dedicated apaa-test- anchor ID.")
    first = client_factory()
    initial = first.read()
    if initial != AnchorState(0, None, None):
        raise RemoteAnchorError("Test anchor must be pre-provisioned at revision zero; refusing to overwrite.")

    candidates = [
        AnchorState(1, hashlib.sha256(os.urandom(32)).hexdigest(), "apaa-test-writer-a"),
        AnchorState(1, hashlib.sha256(os.urandom(32)).hexdigest(), "apaa-test-writer-b"),
    ]

    def contender(target: AnchorState) -> tuple[AnchorState, bool]:
        client = client_factory()
        return target, client.compare_and_advance(expected=initial, target=target)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(contender, candidates))
    winners = [target for target, accepted in results if accepted is True]
    if len(winners) != 1:
        raise RemoteAnchorError("External anchor did not produce exactly one CAS winner.")
    observed = client_factory().read()
    if observed != winners[0]:
        raise RemoteAnchorError("Authoritative read-back did not match the unique CAS winner.")
    loser = candidates[0] if candidates[1] == winners[0] else candidates[1]
    if client_factory().compare_and_advance(expected=initial, target=loser) is not False:
        raise RemoteAnchorError("Stale compare-and-advance was not rejected.")
    restarted = client_factory().read()
    if restarted != winners[0]:
        raise RemoteAnchorError("Fresh client did not observe the durable committed anchor state.")
    return {
        "status": "REMOTE_ANCHOR_ATOMIC_CAS_CONFORMANCE_PASS",
        "test_anchor_id": test_anchor_id,
        "initial_revision": 0,
        "final_revision": restarted.revision,
        "concurrent_writers": 2,
        "successful_writers": 1,
        "stale_write": "REJECTED",
        "fresh_client_readback": "PASS",
        "provider_backup_restore_anti_rollback": "NOT_ASSESSED",
        "independent_administration": "NOT_ASSESSED",
        "independent_review": "PENDING",
        "production_qualification": "NOT_QUALIFIED",
    }


def main(argv: list[str] | None = None, *, anchor_class=HTTPSMonotonicAnchor) -> int:
    parser = argparse.ArgumentParser(description="Explicit external anchor CAS conformance test")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--client-cert", required=True)
    parser.add_argument("--client-key", required=True)
    parser.add_argument("--test-anchor-id", required=True)
    parser.add_argument("--confirm-write-tests", action="store_true")
    parser.add_argument("--server-cert-sha256", default=None)
    args = parser.parse_args(argv)
    if not args.confirm_write_tests:
        print("Refusing remote writes without --confirm-write-tests.", file=sys.stderr)
        return 2
    if not args.test_anchor_id.startswith("apaa-test-"):
        print("Refusing to write: --test-anchor-id must start with apaa-test-.", file=sys.stderr)
        return 2
    def factory():
        return anchor_class(
            endpoint=args.endpoint, ca_file=args.ca_file,
            client_cert=args.client_cert, client_key=args.client_key,
            anchor_id=args.test_anchor_id, server_cert_sha256=args.server_cert_sha256,
        )
    try:
        result = run_conformance(client_factory=factory, test_anchor_id=args.test_anchor_id)
        print(json.dumps({"schema_version": 1, **result}, sort_keys=True, indent=2))
        return 0
    except (RemoteAnchorError, ValueError, TypeError):
        print("Remote anchor conformance failed closed; provider was not qualified.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
