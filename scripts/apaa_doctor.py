"""Run read-only APAA Personal Edition local-runtime diagnostics."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.personal_diagnostics import diagnostics_summary, inspect_personal_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("APAA_PERSONAL_DATA_DIR", Path.home() / ".apaa_personal")),
    )
    args = parser.parse_args()

    results = inspect_personal_runtime(args.data_dir)
    for item in results:
        print(f"[{item.status}] {item.code}: {item.detail}")

    passed, failed, info = diagnostics_summary(results)
    print(f"Summary: {passed} PASS, {failed} FAIL, {info} INFO")
    print("Read-only check: no database, key, Owner account, or application state was changed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
