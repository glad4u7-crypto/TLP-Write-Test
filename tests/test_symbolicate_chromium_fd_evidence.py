import json
import subprocess
from pathlib import Path

import pytest

from scripts import symbolicate_chromium_fd_evidence as symbolicator


BUILD_ID = "4a74f6497529d42bb61262c76d7b1add49c4dea6"


def _evidence(path: Path):
    payload = {
        "chromium_binary_build_id": BUILD_ID,
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


def test_symbolicator_resolves_exact_build_id_and_chromium_stack_frames(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    debug_file = tmp_path / "chromium.debug"
    debug_file.write_bytes(b"debug-info")
    calls = []

    def fake_which(name):
        return name if name in {"debuginfod-find", "eu-addr2line"} else None

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "debuginfod-find":
            return subprocess.CompletedProcess(command, 0, str(debug_file) + "\\n", "")
        return subprocess.CompletedProcess(
            command, 0,
            "base::File::Close()\\nbase/files/file_posix.cc:321\\n"
            "base::ScopedFD::~ScopedFD()\\nbase/files/scoped_file.cc:77\\n",
            "",
        )

    monkeypatch.setattr(symbolicator.shutil, "which", fake_which)
    monkeypatch.setattr(symbolicator.subprocess, "run", fake_run)

    result = symbolicator.symbolicate_evidence_file(evidence_path)
    updated = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result["status"] == "symbols_resolved"
    assert result["build_id"] == BUILD_ID
    assert len(result["frames"]) == 2
    assert result["frames"][0]["function"] == "base::File::Close()"
    assert result["frames"][0]["location"] == "base/files/file_posix.cc:321"
    assert updated["chromium_local_dump_dom"]["failure"]["symbolication"]["status"] == "symbols_resolved"
    assert len(calls) == 2
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


def test_symbolicator_records_debuginfod_not_found_as_nonfatal(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    monkeypatch.setattr(symbolicator.shutil, "which", lambda name: name if name == "debuginfod-find" else None)
    monkeypatch.setattr(
        symbolicator.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "not found"),
    )

    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "debug_info_not_found"


def test_symbolicator_records_debuginfod_timeout_as_nonfatal(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    monkeypatch.setattr(symbolicator.shutil, "which", lambda name: "debuginfod-find" if name == "debuginfod-find" else None)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))

    monkeypatch.setattr(symbolicator.subprocess, "run", timeout)
    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "debuginfod_timeout"


def test_symbolicator_records_addr2line_timeout_without_failing(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evidence.json"
    _evidence(evidence_path)
    debug_file = tmp_path / "chromium.debug"
    debug_file.write_bytes(b"debug-info")
    monkeypatch.setattr(symbolicator.shutil, "which", lambda name: name if name in {"debuginfod-find", "eu-addr2line"} else None)

    def fake_run(command, **kwargs):
        if command[0] == "debuginfod-find":
            return subprocess.CompletedProcess(command, 0, str(debug_file) + "\\n", "")
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))

    monkeypatch.setattr(symbolicator.subprocess, "run", fake_run)
    result = symbolicator.symbolicate_evidence_file(evidence_path)
    assert result["status"] == "symbolication_timeout"
