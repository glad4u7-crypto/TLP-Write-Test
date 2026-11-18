import json
import subprocess
from pathlib import Path

import pytest

from scripts import symbolicate_chromium_fd_evidence as symbolicator


BUILD_ID = "4a74f6497529d42bb61262c76d7b1add49c4dea6"
PACKAGE_VERSION = "156.0.8078.79-1~deb12u1"


def _evidence(path: Path):
    payload = {
        "chromium_binary_build_id": BUILD_ID,
        "chromium_package_version": PACKAGE_VERSION,
        "chromium_package_architecture": "amd64",
        "chromium_local_dump_dom": {
            "failure": {
                "process_mapping": {
                    "stack_frames_with_module_offsets": [
                        {"frame": 0, "module": "chromium", "module_offset": "0x9c6343e"},
                        {"frame": 1, "module": "chromium", "module_offset": "0x9c5a19c"},
                        {"frame": 2, "module": "libc.so.6", "module_offset": "0x1234"},
                    ]
                },
                "symbolication": {"status": "debug-info-not-found"},
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _resolved_stdout():
    return (
        "base::File::Close()\nbase/files/file_posix.cc:321\n"
        "base::ScopedFD::~ScopedFD()\nbase/files/scoped_file.cc:77\n"
    )


def test_symbolicator_resolves_exact_build_id_from_debuginfod(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    debug_file = tmp_path / "chromium.debug"
    debug_file.write_bytes(b"debug-info")
    calls = []

    def fake_which(name):
        return name if name in {"debuginfod-find", "eu-readelf", "eu-addr2line"} else None

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "debuginfod-find":
            return subprocess.CompletedProcess(command, 0, str(debug_file) + "\n", "")
        if command[0] == "eu-readelf":
            return subprocess.CompletedProcess(command, 0, f"Build ID: {BUILD_ID}\n", "")
        return subprocess.CompletedProcess(command, 0, _resolved_stdout(), "")

    monkeypatch.setattr(symbolicator.shutil, "which", fake_which)
    monkeypatch.setattr(symbolicator.subprocess, "run", fake_run)

    result = symbolicator.symbolicate_evidence_file(evidence_path)
    updated = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result["status"] == "symbols_resolved"
    assert result["build_id"] == BUILD_ID
    assert result["source"] == "debuginfod.debian.net"
    assert len(result["frames"]) == 2
    assert result["frames"][0]["function"] == "base::File::Close()"
    assert result["frames"][0]["location"] == "base/files/file_posix.cc:321"
    assert updated["chromium_local_dump_dom"]["failure"]["symbolication"]["status"] == "symbols_resolved"
    assert len(calls) == 3
    assert calls[0][0][1:] == ["debuginfo", BUILD_ID]
    assert calls[0][1]["env"]["DEBUGINFOD_URLS"] == "https://debuginfod.debian.net"


def test_symbolicator_records_missing_build_id_without_network_call(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    payload = _evidence(evidence_path)
    payload["chromium_binary_build_id"] = "not-a-build-id"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(symbolicator.subprocess, "run", lambda *a, **k: pytest.fail("network call not expected"))

    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "invalid_or_missing_build_id"


def test_symbolicator_records_debuginfod_not_found_without_matching_dbgsym(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    payload = _evidence(evidence_path)
    payload.pop("chromium_package_version")
    payload.pop("chromium_package_architecture")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(symbolicator.shutil, "which", lambda name: name if name == "debuginfod-find" else None)
    monkeypatch.setattr(
        symbolicator.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "not found"),
    )

    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "debug_info_not_found"
    assert result["debuginfod_status"] == "debuginfod-not-found"


def test_symbolicator_falls_back_to_exact_debian_security_dbgsym_package(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    calls = []
    debug_file_holder = {}

    def fake_which(name):
        return name if name in {"debuginfod-find", "curl", "dpkg-deb", "eu-readelf", "eu-addr2line"} else None

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "debuginfod-find":
            return subprocess.CompletedProcess(command, 1, "", "not found")
        if command[0] == "curl":
            package_path = Path(command[command.index("-o") + 1])
            package_path.write_bytes(b"debian-package")
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "dpkg-deb":
            extract_root = Path(command[-1])
            debug_file = extract_root / "usr/lib/debug/.build-id" / BUILD_ID[:2] / (BUILD_ID[2:] + ".debug")
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            debug_file.write_bytes(b"exact-build-debug-info")
            debug_file_holder["path"] = debug_file
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "eu-readelf":
            return subprocess.CompletedProcess(command, 0, f"Build ID: {BUILD_ID}\n", "")
        return subprocess.CompletedProcess(command, 0, _resolved_stdout(), "")

    monkeypatch.setattr(symbolicator.shutil, "which", fake_which)
    monkeypatch.setattr(symbolicator.subprocess, "run", fake_run)

    result = symbolicator.symbolicate_evidence_file(evidence_path)

    assert result["status"] == "symbols_resolved"
    assert result["source"] == "debian-security-debug-package"
    assert result["security_dbgsym_package_version"] == PACKAGE_VERSION
    assert result["security_dbgsym_architecture"] == "amd64"
    curl_call = next(command for command, _kwargs in calls if command[0] == "curl")
    assert f"chromium-dbgsym_{PACKAGE_VERSION}_amd64.deb" in curl_call[-1]
    addr2line_call = next(command for command, _kwargs in calls if command[0] == "eu-addr2line")
    assert BUILD_ID[2:] + ".debug" in addr2line_call[-2]
    assert result["debug_info_size_bytes"] == len(b"exact-build-debug-info")


def test_symbolicator_records_debuginfod_timeout_as_nonfatal(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    payload = _evidence(evidence_path)
    payload.pop("chromium_package_version")
    payload.pop("chromium_package_architecture")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(symbolicator.shutil, "which", lambda name: "debuginfod-find" if name == "debuginfod-find" else None)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))

    monkeypatch.setattr(symbolicator.subprocess, "run", timeout)
    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "debug_info_not_found"
    assert result["debuginfod_status"] == "debuginfod-timeout"


def test_symbolicator_records_addr2line_timeout_without_failing(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    debug_file = tmp_path / "chromium.debug"
    debug_file.write_bytes(b"debug-info")
    monkeypatch.setattr(
        symbolicator.shutil, "which",
        lambda name: name if name in {"debuginfod-find", "eu-readelf", "eu-addr2line"} else None,
    )

    def fake_run(command, **kwargs):
        if command[0] == "debuginfod-find":
            return subprocess.CompletedProcess(command, 0, str(debug_file) + "\n", "")
        if command[0] == "eu-readelf":
            return subprocess.CompletedProcess(command, 0, f"Build ID: {BUILD_ID}\n", "")
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))

    monkeypatch.setattr(symbolicator.subprocess, "run", fake_run)
    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "symbolication_timeout"
