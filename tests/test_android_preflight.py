from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.apaa_android_preflight import (
    PreflightError,
    check_streamlit,
    prepare_private_data_dir,
    validate_port,
)


@pytest.mark.parametrize("raw,expected", [("1024", 1024), ("8501", 8501), ("65535", 65535)])
def test_valid_android_ports(raw, expected):
    assert validate_port(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "85.01", "-1", "1023", "65536", "１２３４"])
def test_invalid_android_ports_are_rejected(raw):
    with pytest.raises(PreflightError):
        validate_port(raw)


def test_relative_data_directory_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PreflightError, match="absolute path"):
        prepare_private_data_dir(".apaa_personal")


def test_private_data_directory_is_created_with_owner_only_permissions(tmp_path):
    target = tmp_path / "private" / ".apaa_personal"
    result = prepare_private_data_dir(target)
    assert result == target
    assert target.is_dir()
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o700
        assert target.stat().st_uid == os.getuid()


def test_existing_directory_permissions_are_restricted(tmp_path):
    target = tmp_path / ".apaa_personal"
    target.mkdir(mode=0o755)
    if os.name == "posix":
        target.chmod(0o755)
        prepare_private_data_dir(target)
        assert target.stat().st_mode & 0o777 == 0o700


def test_symlink_data_directory_is_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    link = tmp_path / ".apaa_personal"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises((PreflightError, OSError)):
        prepare_private_data_dir(link)


def test_regular_file_data_path_is_rejected(tmp_path):
    target = tmp_path / ".apaa_personal"
    target.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PreflightError):
        prepare_private_data_dir(target)


def test_streamlit_dependency_check_fails_closed_when_missing(monkeypatch):
    monkeypatch.setattr("scripts.apaa_android_preflight.importlib.util.find_spec", lambda name: None)
    with pytest.raises(PreflightError, match="Streamlit is not installed"):
        check_streamlit()
