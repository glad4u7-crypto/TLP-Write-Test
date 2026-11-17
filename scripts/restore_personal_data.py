"""Restore an APAA Personal Edition backup into a new private data directory."""
from __future__ import annotations

import argparse
from pathlib import Path

from core.personal_backup import PersonalBackupError, restore_personal_backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = restore_personal_backup(args.backup, args.destination)
    except PersonalBackupError as exc:
        print(f"Restore failed safely: {exc}")
        return 2
    print(f"APAA Personal Edition data restored: {result}")
    print("Set APAA_PERSONAL_DATA_DIR to this directory before restarting APAA.")
    print("A fresh approval signing key was generated; outstanding approvals are invalid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
