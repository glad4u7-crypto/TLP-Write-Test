#!/usr/bin/env python3
"""Read-only connectivity and schema preflight for the external APAA anchor API.

This verifies mTLS reachability and current state only. It does not write,
bootstrap, advance, reset, or qualify provider backup/restore behavior.
"""
from __future__ import annotations

import argparse
import json
import sys

from core.remote_owner_anchor import HTTPSMonotonicAnchor, RemoteAnchorError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only APAA external monotonic-anchor preflight")
    parser.add_argument("--endpoint", required=True, help="HTTPS base URL for the anchor service")
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--client-cert", required=True)
    parser.add_argument("--client-key", required=True, help="Private key file; POSIX mode 0600 required")
    parser.add_argument("--anchor-id", required=True)
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--server-cert-sha256", default=None)
    args = parser.parse_args(argv)
    try:
        anchor = HTTPSMonotonicAnchor(
            endpoint=args.endpoint, ca_file=args.ca_file,
            client_cert=args.client_cert, client_key=args.client_key,
            anchor_id=args.anchor_id, server_cert_sha256=args.server_cert_sha256,
        )
        state = anchor.read()
        sequence = anchor.read_sequence(args.issuer_id)
        print(json.dumps({
            "schema_version": 1,
            "status": "SERVICE_REACHABLE_SCHEMA_VALID",
            "owner_anchor": {
                "revision": state.revision,
                "generation": state.generation,
                "change_id": state.change_id,
            },
            "trust_bundle_issuer": args.issuer_id,
            "trust_bundle_sequence": sequence,
            "write_test": "NOT_RUN",
            "backup_restore_anti_rollback": "NOT_ASSESSED",
            "independent_administration": "NOT_ASSESSED",
            "independent_review": "PENDING",
            "production_qualification": "NOT_QUALIFIED",
        }, sort_keys=True, indent=2))
        return 0
    except (RemoteAnchorError, ValueError, TypeError):
        print("External anchor preflight failed closed; no state was changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
