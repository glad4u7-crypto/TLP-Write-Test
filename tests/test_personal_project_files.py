from __future__ import annotations

import os

import pytest

from core.personal_project_files import (
    ProjectFileError,
    list_project_files,
    project_files_directory,
    save_project_file,
)


def test_project_file_save_requires_explicit_consent(tmp_path):
    with pytest.raises(PermissionError, match="consent"):
        save_project_file(tmp_path / "owner-data", "project-1", "notes.md", b"hello")
    assert not (tmp_path / "owner-data").exists()


def test_owner_approved_file_is_private_and_listed_with_hash(tmp_path):
    root = tmp_path / "owner-data"
    entry = save_project_file(root, "project-1", "notes.md", b"# Private notes\n", consent=True)
    assert entry.name == "notes.md"
    assert entry.size == len(b"# Private notes\n")
    assert len(entry.sha256) == 64
    directory = project_files_directory(root, "project-1")
    assert (directory / "notes.md").read_bytes() == b"# Private notes\n"
    if os.name == "posix":
        assert (directory.stat().st_mode & 0o777) == 0o700
        assert ((directory / "notes.md").stat().st_mode & 0o777) == 0o600
    assert list_project_files(root, "project-1") == [entry]


def test_project_file_overwrite_is_blocked(tmp_path):
    root = tmp_path / "owner-data"
    save_project_file(root, "project-1", "notes.md", b"first", consent=True)
    with pytest.raises(ProjectFileError, match="overwrite is disabled"):
        save_project_file(root, "project-1", "notes.md", b"second", consent=True)
    assert (project_files_directory(root, "project-1") / "notes.md").read_bytes() == b"first"


@pytest.mark.parametrize("filename", [
    "../outside.txt", "/absolute.txt", "folder/file.txt", "secret.env",
    ".hidden.txt", "C:\\outside.txt",
])
def test_unsafe_project_filenames_are_rejected(tmp_path, filename):
    with pytest.raises(ProjectFileError):
        save_project_file(tmp_path / "owner-data", "project-1", filename, b"hello", consent=True)


def test_project_file_rejects_binary_oversized_and_credential_like_content(tmp_path):
    root = tmp_path / "owner-data"
    with pytest.raises(ProjectFileError, match="UTF-8"):
        save_project_file(root, "project-1", "binary.txt", b"\xff", consent=True)
    with pytest.raises(ProjectFileError, match="65536"):
        save_project_file(root, "project-1", "large.txt", b"x" * 65537, consent=True)
    with pytest.raises(ProjectFileError, match="credential-like"):
        save_project_file(root, "project-1", "secret.txt", b"password=do-not-store", consent=True)


def test_project_file_listing_never_follows_symlinked_file(tmp_path):
    root = tmp_path / "owner-data"
    save_project_file(root, "project-1", "safe.txt", b"safe", consent=True)
    directory = project_files_directory(root, "project-1")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside private file", encoding="utf-8")
    (directory / "link.txt").symlink_to(outside)
    entries = list_project_files(root, "project-1")
    assert [entry.name for entry in entries] == ["safe.txt"]


def test_project_file_root_symlink_is_rejected_for_reading(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ProjectFileError, match="symlinks"):
        project_files_directory(linked, "project-1", create=False)
