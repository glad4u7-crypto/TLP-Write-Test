"""Best-effort exact-build Chromium symbolication using Debian debuginfod.

The helper never fails the disposable-host qualification if symbols are absent.
It writes only function/location strings and build metadata into the sanitized
evidence JSON; the downloaded debug file is not included in the artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


_BUILD_ID = re.compile(r"^[0-9a-f]{40}$")
_OFFSET = re.compile(r"^0x[0-9a-fA-F]+$")


def _stack_frames(failure: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = failure.get("process_mapping")
    if not isinstance(mapping, dict):
        return []
    frames = mapping.get("stack_frames_with_module_offsets")
    if not isinstance(frames, list):
        return []
    return [
        frame for frame in frames
        if isinstance(frame, dict)
        and frame.get("module") == "chromium"
        and isinstance(frame.get("module_offset"), str)
        and _OFFSET.fullmatch(frame["module_offset"])
    ]


def _run_addr2line(debug_file: Path, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolver = shutil.which("eu-addr2line") or shutil.which("addr2line")
    if not resolver:
        return []
    offsets = [frame["module_offset"] for frame in frames]
    completed = subprocess.run(
        [resolver, "-f", "-C", "-e", str(debug_file), *offsets],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if completed.returncode != 0:
        return []
    lines = completed.stdout.splitlines()
    resolved: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        function = lines[index * 2] if index * 2 < len(lines) else "??"
        location = lines[index * 2 + 1] if index * 2 + 1 < len(lines) else "??:0"
        resolved.append({
            "frame": frame.get("frame"),
            "offset": frame["module_offset"],
            "function": function[:512],
            "location": location[:512],
        })
    return resolved


def symbolicate_evidence_file(evidence_path: str | Path) -> dict[str, Any]:
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    build_id = evidence.get("chromium_binary_build_id")
    failure = evidence.get("chromium_local_dump_dom", {}).get("failure")
    if not isinstance(failure, dict):
        return {"status": "no_chromium_failure_record"}
    if not isinstance(build_id, str) or not _BUILD_ID.fullmatch(build_id):
        result = {"status": "invalid_or_missing_build_id"}
        failure["symbolication"] = result
        path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result

    client = shutil.which("debuginfod-find")
    if not client:
        result = {"status": "debuginfod_client_unavailable", "build_id": build_id}
        failure["symbolication"] = result
        path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result

    env = os.environ.copy()
    env["DEBUGINFOD_URLS"] = "https://debuginfod.debian.net"
    env["DEBUGINFOD_PROGRESS"] = "0"
    try:
        fetched = subprocess.run(
            [client, "debuginfo", build_id],
            capture_output=True, text=True, timeout=120, check=False, env=env,
        )
    except subprocess.TimeoutExpired:
        result = {"status": "debuginfod_timeout", "build_id": build_id}
        failure["symbolication"] = result
        path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result

    debug_path_text = fetched.stdout.strip().splitlines()[-1] if fetched.stdout.strip() else ""
    debug_file = Path(debug_path_text) if debug_path_text else None
    if fetched.returncode != 0 or debug_file is None or not debug_file.is_file():
        result = {
            "status": "debug_info_not_found",
            "build_id": build_id,
            "source": "debuginfod.debian.net",
            "client_exit_code": fetched.returncode,
        }
        failure["symbolication"] = result
        path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result

    frames = _stack_frames(failure)
    try:
        resolved = _run_addr2line(debug_file, frames)
    except subprocess.TimeoutExpired:
        resolved = []
        status = "symbolication_timeout"
    else:
        status = (
            "symbols_resolved"
            if any(item["function"] != "??" or item["location"] not in {"??:0", "??:?"} for item in resolved)
            else "debug_info_found_no_symbols"
        )
    debug_bytes = debug_file.read_bytes()
    result = {
        "status": status,
        "build_id": build_id,
        "source": "debuginfod.debian.net",
        "debug_info_size_bytes": len(debug_bytes),
        "debug_info_sha256": hashlib.sha256(debug_bytes).hexdigest(),
        "frames": resolved,
    }
    failure["symbolication"] = result
    path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: symbolicate_chromium_fd_evidence.py EVIDENCE_JSON", file=sys.stderr)
        return 2
    try:
        result = symbolicate_evidence_file(args[0])
    except Exception as exc:  # best-effort; never fail the OCI qualification
        print(f"symbolication helper error: {type(exc).__name__}", file=sys.stderr)
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
