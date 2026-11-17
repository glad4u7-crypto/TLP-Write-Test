"""Create an owner-private APAA Personal Edition backup."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.personal_backup import PersonalBackupError, create_personal_backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("APAA_PERSONAL_DATA_DIR", Path.home() / ".apaa_personal")),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create_personal_backup(args.data_dir, args.output)
    except PersonalBackupError as exc:
        print(f"Backup failed safely: {exc}")
        return 2
    print(f"APAA Personal Edition backup created: {result}")
    print("The approval signing key is not included; restore generates a fresh key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
