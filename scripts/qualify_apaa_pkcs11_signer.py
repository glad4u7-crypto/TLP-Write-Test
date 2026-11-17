#!/usr/bin/env python3
"""Read-only self-test for an already provisioned Ed25519 PKCS#11 token key.

This script does not create, import, rotate or delete keys. It prompts for the
token PIN without echo, validates non-extractability attributes through the
adapter, signs a random challenge and verifies it locally.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.pkcs11_ed25519_signer import PKCS11Ed25519InspectorSigner, PKCS11SignerError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only APAA PKCS#11 Ed25519 signer qualification")
    parser.add_argument("--module", required=True, help="Absolute path to PKCS#11 shared library")
    parser.add_argument("--token-label", required=True)
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args(argv)

    pin = getpass.getpass("PKCS#11 user PIN (input hidden): ")
    try:
        signer = PKCS11Ed25519InspectorSigner(
            module_path=args.module, token_label=args.token_label,
            key_id=args.key_id, user_pin=pin,
        )
        public = signer.public_key_bytes()
        challenge = b"APAA-PKCS11-QUALIFICATION-V1:" + os.urandom(32)
        signature = signer.sign(challenge)
        Ed25519PublicKey.from_public_bytes(public).verify(signature, challenge)
        result = {
            "schema_version": 1,
            "status": "TOKEN_SIGNER_SELF_TEST_PASS",
            "algorithm": "Ed25519",
            "key_id": signer.key_id,
            "public_key_sha256": hashlib.sha256(public).hexdigest(),
            "private_key_export": "NOT_REQUESTED",
            "token_hardware_identity": "NOT_INDEPENDENTLY_VERIFIED",
            "backup_restore_qualification": "NOT_ASSESSED",
            "independent_review": "PENDING",
        }
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (PKCS11SignerError, InvalidSignature, ValueError, TypeError):
        print("PKCS#11 signer self-test failed closed; no qualification evidence was produced.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
