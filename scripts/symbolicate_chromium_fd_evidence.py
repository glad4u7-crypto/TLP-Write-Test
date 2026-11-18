"""Best-effort exact-build Chromium symbolication from Debian debug sources.

The helper never fails the disposable-host qualification if symbols are absent.
It writes only function/location strings and build metadata into the sanitized
evidence JSON; downloaded debug packages/files are not included in the artifact.
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
import tempfile
from typing import Any
from urllib.parse import quote


_BUILD_ID = re.compile(r"^[0-9a-f]{40}$")
_OFFSET = re.compile(r"^0x[0-9a-fA-F]+$")
_PACKAGE_VERSION = re.compile(r"^[0-9A-Za-z.+:~_-]{1,128}$")
_ARCHITECTURES = {"amd64", "arm64", "i386", "ppc64el"}


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


def _verify_build_id(debug_file: Path, build_id: str) -> bool:
    readelf = shutil.which("eu-readelf") or shutil.which("readelf")
    if not readelf:
        return False
    try:
        result = subprocess.run(
            [readelf, "-n", str(debug_file)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    match = re.search(r"Build ID:\s*([0-9a-f]+)", result.stdout, re.IGNORECASE)
    return bool(match and match.group(1).lower() == build_id)


def _fetch_debuginfod(build_id: str) -> tuple[Path | None, str, int | None]:
    client = shutil.which("debuginfod-find")
    if not client:
        return None, "debuginfod-client-unavailable", None
    env = os.environ.copy()
    env["DEBUGINFOD_URLS"] = "https://debuginfod.debian.net"
    env["DEBUGINFOD_PROGRESS"] = "0"
    try:
        result = subprocess.run(
            [client, "debuginfo", build_id],
            capture_output=True, text=True, timeout=120, check=False, env=env,
        )
    except subprocess.TimeoutExpired:
        return None, "debuginfod-timeout", None
    path_text = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    debug_file = Path(path_text) if path_text else None
    if result.returncode != 0 or debug_file is None or not debug_file.is_file():
        return None, "debuginfod-not-found", result.returncode
    return debug_file, "debuginfod.debian.net", result.returncode


def _fetch_security_dbgsym(
    build_id: str,
    package_version: str | None,
    architecture: str | None,
    temp_root: Path,
) -> tuple[Path | None, str, int | None]:
    if (
        not isinstance(package_version, str)
        or not _PACKAGE_VERSION.fullmatch(package_version)
        or architecture not in _ARCHITECTURES
    ):
        return None, "invalid_package_metadata", None
    curl = shutil.which("curl")
    dpkg_deb = shutil.which("dpkg-deb")
    if not curl:
        return None, "curl_unavailable", None
    if not dpkg_deb:
        return None, "dpkg_deb_unavailable", None

    package_name = f"chromium-dbgsym_{package_version}_{architecture}.deb"
    url = (
        "https://deb.debian.org/debian-security-debug/pool/updates/main/c/chromium/"
        + quote(package_name, safe="~._-")
    )
    package_path = temp_root / package_name
    try:
        downloaded = subprocess.run(
            [
                curl, "-fL", "--retry", "2", "--connect-timeout", "10",
                "--max-time", "120", "--max-filesize", "100000000",
                "-o", str(package_path), url,
            ],
            capture_output=True, text=True, timeout=130, check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "download_timeout", None
    except OSError:
        return None, "download_tool_error", None
    if downloaded.returncode != 0:
        return None, "download_failed", downloaded.returncode
    if not package_path.is_file():
        return None, "download_file_missing", downloaded.returncode

    extract_root = temp_root / "dbgsym"
    try:
        extracted = subprocess.run(
            [dpkg_deb, "-x", str(package_path), str(extract_root)],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "extract_timeout", None
    except OSError:
        return None, "extract_tool_error", None
    if extracted.returncode != 0:
        return None, "extract_failed", extracted.returncode

    expected = (
        extract_root / "usr/lib/debug/.build-id" / build_id[:2]
        / (build_id[2:] + ".debug")
    )
    if not expected.is_file():
        candidates = list(extract_root.rglob(build_id[2:] + ".debug"))
        expected = candidates[0] if candidates else expected
    if not expected.is_file():
        return None, "build_id_debug_file_missing", 0
    if not _verify_build_id(expected, build_id):
        return None, "build_id_mismatch_or_unverifiable", 0
    return expected, "exact_build_id_verified", 0

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


def _write_result(path: Path, evidence: dict[str, Any], failure: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    failure["symbolication"] = result
    path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def symbolicate_evidence_file(evidence_path: str | Path) -> dict[str, Any]:
    path = Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    build_id = evidence.get("chromium_binary_build_id")
    failure = evidence.get("chromium_local_dump_dom", {}).get("failure")
    if not isinstance(failure, dict):
        return {"status": "no_chromium_failure_record"}
    if not isinstance(build_id, str) or not _BUILD_ID.fullmatch(build_id):
        return _write_result(path, evidence, failure, {"status": "invalid_or_missing_build_id"})

    package_version = evidence.get("chromium_package_version")
    architecture = evidence.get("chromium_package_architecture")
    debuginfod_exit_code = None
    with tempfile.TemporaryDirectory(prefix="apaa-chromium-symbols-") as temp_name:
        temp_root = Path(temp_name)
        debug_file, source, debuginfod_exit_code = _fetch_debuginfod(build_id)
        if debug_file is not None and not _verify_build_id(debug_file, build_id):
            debug_file = None
            source = "debuginfod-build-id-mismatch"

        package_used = False
        dbgsym_status = "not_attempted"
        dbgsym_exit_code = None
        if debug_file is None:
            debug_file, dbgsym_status, dbgsym_exit_code = _fetch_security_dbgsym(
                build_id, package_version, architecture, temp_root,
            )
            if debug_file is not None:
                source = "debian-security-debug-package"
                package_used = True

        if debug_file is None:
            return _write_result(path, evidence, failure, {
                "status": "debug_info_not_found",
                "build_id": build_id,
                "debuginfod_status": source,
                "debuginfod_exit_code": debuginfod_exit_code,
                "security_dbgsym_status": dbgsym_status,
                "security_dbgsym_exit_code": dbgsym_exit_code,
                "security_dbgsym_package_version": package_version,
                "security_dbgsym_architecture": architecture,
            })

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
        size = debug_file.stat().st_size
        digest = hashlib.sha256()
        with debug_file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result = {
            "status": status,
            "build_id": build_id,
            "source": source,
            "debug_info_size_bytes": size,
            "debug_info_sha256": digest.hexdigest(),
            "frames": resolved,
        }
        if package_used:
            result["security_dbgsym_status"] = dbgsym_status
            result["security_dbgsym_package_version"] = package_version
            result["security_dbgsym_architecture"] = architecture
        return _write_result(path, evidence, failure, result)


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
