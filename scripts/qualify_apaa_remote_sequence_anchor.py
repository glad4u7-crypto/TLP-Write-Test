#!/usr/bin/env python3
"""Explicit conformance test for a remote monotonic trust-sequence anchor.

Uses only a pre-provisioned, disposable issuer in the dedicated apaa-test-
namespace. A successful run consumes sequence 0 -> 1 and deliberately does not
provide a reset operation. Provider backup/restore and administrative
independence are not assessed by this runner.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import sys

from core.remote_owner_anchor import HTTPSMonotonicAnchor, RemoteAnchorError


def run_sequence_conformance(*, client_factory, test_issuer_id: str) -> dict[str, object]:
    if type(test_issuer_id) is not str or not test_issuer_id.startswith("apaa-test-"):
        raise RemoteAnchorError("Sequence write qualification requires a dedicated apaa-test- issuer.")
    initial = client_factory().read_sequence(test_issuer_id)
    if initial != 0:
        raise RemoteAnchorError("Test issuer must be pre-provisioned at sequence zero; refusing to overwrite.")

    def contender() -> bool:
        return client_factory().advance_sequence(
            test_issuer_id, expected_current=0, new_sequence=1,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: contender(), range(2)))
    if outcomes.count(True) != 1 or outcomes.count(False) != 1:
        raise RemoteAnchorError("Remote sequence anchor did not produce exactly one CAS winner.")

    observed = client_factory().read_sequence(test_issuer_id)
    if observed != 1:
        raise RemoteAnchorError("Authoritative sequence read-back did not match the committed value.")

    if client_factory().advance_sequence(
        test_issuer_id, expected_current=0, new_sequence=1,
    ) is not False:
        raise RemoteAnchorError("Stale sequence compare-and-advance was not rejected.")

    restarted_value = client_factory().read_sequence(test_issuer_id)
    if restarted_value != 1:
        raise RemoteAnchorError("Fresh client did not observe the committed monotonic sequence.")

    return {
        "status": "REMOTE_SEQUENCE_ANCHOR_CAS_CONFORMANCE_PASS",
        "test_issuer_id": test_issuer_id,
        "initial_sequence": 0,
        "final_sequence": restarted_value,
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
    parser = argparse.ArgumentParser(description="Explicit remote trust-sequence anchor CAS conformance test")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--client-cert", required=True)
    parser.add_argument("--client-key", required=True)
    parser.add_argument("--test-issuer-id", required=True)
    parser.add_argument("--confirm-write-tests", action="store_true")
    parser.add_argument("--server-cert-sha256", default=None)
    args = parser.parse_args(argv)

    if not args.confirm_write_tests:
        print("Refusing remote writes without --confirm-write-tests.", file=sys.stderr)
        return 2
    if not args.test_issuer_id.startswith("apaa-test-"):
        print("Refusing to write: --test-issuer-id must start with apaa-test-.", file=sys.stderr)
        return 2

    def factory():
        return anchor_class(
            endpoint=args.endpoint,
            ca_file=args.ca_file,
            client_cert=args.client_cert,
            client_key=args.client_key,
            anchor_id="apaa-test-sequence-client",
            server_cert_sha256=args.server_cert_sha256,
        )

    try:
        result = run_sequence_conformance(
            client_factory=factory,
            test_issuer_id=args.test_issuer_id,
        )
        print(json.dumps({"schema_version": 1, **result}, sort_keys=True, indent=2))
        return 0
    except (RemoteAnchorError, ValueError, TypeError):
        print("Remote sequence-anchor conformance failed closed; provider was not qualified.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
