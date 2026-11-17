"""Owner-approved, bounded project-local text file storage for APAA Personal Edition."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat

from core.personal_runtime import ensure_private_data_dir

MAX_PROJECT_FILE_BYTES = 64 * 1024
_ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".log"}
_SECRET_PATTERN = re.compile(
    r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,})"
)


class ProjectFileError(ValueError):
    """Raised when a project file cannot be safely stored or inspected."""


@dataclass(frozen=True)
class ProjectFileEntry:
    name: str
    size: int
    sha256: str


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            if stat.S_ISLNK(component.lstat().st_mode):
                raise ProjectFileError("Project file path must not contain symlinks.")
        except FileNotFoundError:
            continue


def _validate_project_id(project_id: object) -> str:
    if not isinstance(project_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project_id) is None:
        raise ProjectFileError("Project ID is invalid.")
    return project_id


def _validate_filename(filename: object) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 120
        or filename != filename.strip()
        or filename.startswith(".")
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or any(ord(char) < 32 for char in filename)
        or Path(filename).name != filename
        or Path(filename).suffix.lower() not in _ALLOWED_SUFFIXES
    ):
        raise ProjectFileError("Only safe, simple UTF-8 text filenames with approved extensions are allowed.")
    return filename


def project_files_directory(
    data_dir: str | os.PathLike[str], project_id: str, *, create: bool = False,
) -> Path:
    """Resolve the private project-files directory without following symlinks."""
    project_id = _validate_project_id(project_id)
    root = Path(data_dir).expanduser().absolute()
    if create:
        ensure_private_data_dir(root)
    else:
        _reject_symlink_components(root)
    files_root = root / "project-files"
    if create:
        ensure_private_data_dir(files_root)
    else:
        try:
            metadata = files_root.lstat()
        except FileNotFoundError:
            raise ProjectFileError("This project has no stored files yet.") from None
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ProjectFileError("Project files root is not a safe directory.")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ProjectFileError("Project files root is not owner-private.")
    project_root = files_root / project_id
    if create:
        ensure_private_data_dir(project_root)
    else:
        try:
            metadata = project_root.lstat()
        except FileNotFoundError:
            raise ProjectFileError("This project has no stored files yet.") from None
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ProjectFileError("Project file directory is not a safe directory.")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ProjectFileError("Project file directory is not owner-private.")
    return project_root


def save_project_file(
    data_dir: str | os.PathLike[str], project_id: str, filename: str,
    content: bytes, *, consent: bool = False,
) -> ProjectFileEntry:
    """Create a new file atomically; never overwrite an existing project file."""
    if consent is not True:
        raise PermissionError("Explicit Owner consent is required to save a project file.")
    project_id = _validate_project_id(project_id)
    filename = _validate_filename(filename)
    if not isinstance(content, bytes) or not 1 <= len(content) <= MAX_PROJECT_FILE_BYTES:
        raise ProjectFileError("Project file must contain 1 to 65536 bytes.")
    try:
        decoded = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ProjectFileError("Only UTF-8 text files can be stored.") from None
    if "\x00" in decoded or _SECRET_PATTERN.search(decoded):
        raise ProjectFileError("Binary, null-containing, or credential-like content is not accepted.")

    directory = project_files_directory(data_dir, project_id, create=True)
    directory_fd = os.open(
        directory,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    descriptor = None
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(filename, flags, 0o600, dir_fd=directory_fd)
        except FileExistsError:
            raise ProjectFileError("A file with this name already exists; overwrite is disabled.") from None
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ProjectFileError("Project file could not be created safely.") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)

    return ProjectFileEntry(filename, len(content), hashlib.sha256(content).hexdigest())


def list_project_files(
    data_dir: str | os.PathLike[str], project_id: str,
) -> list[ProjectFileEntry]:
    directory = project_files_directory(data_dir, project_id, create=False)
    directory_fd = os.open(
        directory,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    entries: list[ProjectFileEntry] = []
    try:
        with os.scandir(directory) as iterator:
            names = sorted((item.name for item in iterator), key=str.casefold)
        for name in names:
            try:
                filename = _validate_filename(name)
                descriptor = os.open(
                    filename,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=directory_fd,
                )
                with os.fdopen(descriptor, "rb") as stream:
                    metadata = os.fstat(stream.fileno())
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_PROJECT_FILE_BYTES:
                        continue
                    content = stream.read(MAX_PROJECT_FILE_BYTES + 1)
                if len(content) > MAX_PROJECT_FILE_BYTES:
                    continue
                try:
                    decoded = content.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    continue
                if "\x00" in decoded or _SECRET_PATTERN.search(decoded):
                    continue
                entries.append(ProjectFileEntry(
                    filename, len(content), hashlib.sha256(content).hexdigest()
                ))
            except (OSError, ProjectFileError):
                continue
    finally:
        os.close(directory_fd)
    return entries
