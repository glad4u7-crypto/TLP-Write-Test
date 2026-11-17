from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.personal_runtime import (
    PERSONAL_OWNER_TENANT,
    SIGNING_KEY_FILENAME,
    ensure_private_data_dir,
    load_or_create_approval_signing_key,
    personal_runtime_paths,
)


def test_personal_runtime_uses_one_fixed_local_owner():
    assert PERSONAL_OWNER_TENANT.issuer == "local://apaa-personal"
    assert PERSONAL_OWNER_TENANT.subject == "local-owner"


def test_personal_runtime_paths_are_grouped_under_owner_data_directory(tmp_path):
    paths = personal_runtime_paths(tmp_path / "private")
    assert paths.projects_db.parent == paths.data_dir
    assert paths.security_db.parent == paths.data_dir
    assert paths.owner_auth_db.parent == paths.data_dir
    assert paths.memory_db.parent == paths.data_dir
    assert paths.audit_log.parent == paths.data_dir
    assert paths.signing_key.name == SIGNING_KEY_FILENAME


def test_local_signing_key_is_stable_across_restarts(tmp_path):
    first = load_or_create_approval_signing_key(tmp_path / "apaa")
    second = load_or_create_approval_signing_key(tmp_path / "apaa")
    assert len(first) == 32
    assert second == first


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are platform-specific")
def test_personal_data_directory_and_key_are_owner_only(tmp_path):
    root = ensure_private_data_dir(tmp_path / "apaa")
    key = load_or_create_approval_signing_key(root)
    assert len(key) == 32
    assert (root.stat().st_mode & 0o777) == 0o700
    assert ((root / SIGNING_KEY_FILENAME).stat().st_mode & 0o777) == 0o600


def test_insecure_existing_directory_is_rejected_without_chmod(tmp_path):
    root = tmp_path / "shared"
    root.mkdir(mode=0o755)
    if os.name == "posix":
        root.chmod(0o755)
        with pytest.raises(ValueError, match="owner-only"):
            ensure_private_data_dir(root)
        assert (root.stat().st_mode & 0o777) == 0o755


def test_symlinked_data_directory_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlinks"):
        ensure_private_data_dir(link)


def test_corrupt_key_is_not_silently_replaced(tmp_path):
    root = ensure_private_data_dir(tmp_path / "apaa")
    path = root / SIGNING_KEY_FILENAME
    path.write_bytes(b"short")
    if os.name == "posix":
        path.chmod(0o600)
    with pytest.raises(ValueError, match="invalid length"):
        load_or_create_approval_signing_key(root)
    assert path.read_bytes() == b"short"
