"""Safe, read-only inspection of ZIP archives without extracting or executing files."""
from __future__ import annotations

import io
import re
import stat
import zipfile
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 500
MAX_TOTAL_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_TEXT_FILE_BYTES = 256 * 1024
MAX_COMPRESSION_RATIO = 100

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".sh",
    ".bat", ".ps1", ".sql", ".xml", ".csv", ".gitignore",
}
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
SECRET_PATTERN = re.compile(
    r"""(?i)\b(?:api[_-]?key|secret|password|token|access[_-]?key)\b\s*[:=]\s*["']?([A-Za-z0-9_./+\-=]{12,})"""
)
RISK_PATTERNS = (
    ("Process execution", re.compile(r"\bsubprocess\b|\bos\.system\s*\(")),
    ("Dynamic code execution", re.compile(r"\b(?:eval|exec)\s*\(")),
    ("Unsafe deserialization", re.compile(r"\bpickle\.loads?\s*\(")),
)


class InspectionError(ValueError):
    """The uploaded archive is invalid or exceeds a safe inspection limit."""


@dataclass(frozen=True)
class InspectedFile:
    path: str
    size_bytes: int
    kind: str
    line_count: int | None = None


@dataclass(frozen=True)
class InspectionReport:
    total_files: int
    text_files: int
    skipped_files: int
    total_uncompressed_bytes: int
    files: tuple[InspectedFile, ...]
    findings: tuple[str, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["files"] = [asdict(item) for item in self.files]
        result["findings"] = list(self.findings)
        return result


def _validate_member(info: zipfile.ZipInfo) -> str:
    """Validate a ZIP member and return a portable collision-detection key."""
    name = info.filename
    if not name or "\\" in name or name.startswith("/") or ":" in name:
        raise InspectionError("Archive contains an unsafe file path.")

    # A trailing slash is valid only for a directory entry. Empty interior
    # segments, dot segments, and parent segments are never accepted.
    candidate = name[:-1] if info.is_dir() and name.endswith("/") else name
    parts = candidate.split("/")
    if not candidate or any(part in {"", ".", ".."} for part in parts):
        raise InspectionError("Archive contains an unsafe file path.")

    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise InspectionError("Archive contains a symbolic link; inspection stopped.")
    if info.flag_bits & 0x1:
        raise InspectionError("Password-protected ZIP files are not supported.")

    # ZIP paths are case-sensitive by specification, but repositories are
    # often unpacked on case-insensitive filesystems. NFC + casefold rejects
    # portable path collisions before an archive is used elsewhere.
    normalized = unicodedata.normalize("NFC", "/".join(parts)).casefold()
    return normalized


def inspect_zip(data: bytes) -> InspectionReport:
    """Inspect ZIP metadata and selected text files; never extract or execute content."""
    if not isinstance(data, bytes) or not data:
        raise InspectionError("Please upload a non-empty ZIP file.")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise InspectionError("ZIP file exceeds the 10 MB upload limit.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError):
        raise InspectionError("The uploaded file is not a valid ZIP archive.") from None

    files: list[InspectedFile] = []
    findings: list[str] = []
    total_bytes = 0
    skipped = 0
    seen_names: set[str] = set()

    try:
        with archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise InspectionError("ZIP contains too many entries (maximum 500).")

            regular_files = [item for item in entries if not item.is_dir()]
            if len(regular_files) > MAX_ENTRIES:
                raise InspectionError("ZIP contains too many files (maximum 500).")

            for info in entries:
                normalized_name = _validate_member(info)
                if normalized_name in seen_names:
                    raise InspectionError("ZIP contains duplicate or colliding file paths.")
                seen_names.add(normalized_name)
                if info.is_dir():
                    continue

                total_bytes += info.file_size
                if total_bytes > MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise InspectionError("ZIP expands beyond the 20 MB inspection limit.")
                if info.file_size < 0 or info.compress_size < 0:
                    raise InspectionError("ZIP contains invalid file metadata.")
                if info.file_size and info.compress_size == 0:
                    raise InspectionError("ZIP contains suspicious compression metadata.")
                if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                    raise InspectionError("ZIP compression ratio is too high; inspection stopped.")

                parts = PurePosixPath(info.filename).parts
                if any(part in IGNORED_DIRS for part in parts[:-1]):
                    skipped += 1
                    files.append(InspectedFile(info.filename, info.file_size, "ignored"))
                    continue

                basename = parts[-1].lower()
                suffix = PurePosixPath(basename).suffix.lower()
                if basename in SENSITIVE_NAMES or basename.startswith(".env."):
                    skipped += 1
                    files.append(InspectedFile(info.filename, info.file_size, "sensitive file skipped"))
                    findings.append(f"{info.filename}: sensitive configuration file skipped; contents were not read.")
                    continue

                if suffix not in TEXT_EXTENSIONS and basename not in {".gitignore", "dockerfile", "makefile"}:
                    skipped += 1
                    files.append(InspectedFile(info.filename, info.file_size, "non-text file skipped"))
                    continue
                if info.file_size > MAX_TEXT_FILE_BYTES:
                    skipped += 1
                    files.append(InspectedFile(info.filename, info.file_size, "large text file skipped"))
                    continue

                try:
                    with archive.open(info, "r") as stream:
                        raw = stream.read(MAX_TEXT_FILE_BYTES + 1)
                except (RuntimeError, zipfile.BadZipFile, OSError):
                    raise InspectionError("A ZIP entry could not be safely read.") from None
                if len(raw) > MAX_TEXT_FILE_BYTES or b"\x00" in raw:
                    skipped += 1
                    files.append(InspectedFile(info.filename, info.file_size, "binary or oversized file skipped"))
                    continue

                text = raw.decode("utf-8", errors="replace")
                line_count = len(text.splitlines())
                files.append(InspectedFile(info.filename, info.file_size, "text", line_count))
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if SECRET_PATTERN.search(line):
                        findings.append(
                            f"{info.filename}:{line_number}: possible credential value detected; value hidden."
                        )
                    for label, pattern in RISK_PATTERNS:
                        if pattern.search(line):
                            findings.append(
                                f"{info.filename}:{line_number}: {label} pattern found; manual review recommended."
                            )
                            break
    except InspectionError:
        raise
    except (RuntimeError, zipfile.BadZipFile, OSError):
        raise InspectionError("The ZIP archive could not be read safely.") from None

    return InspectionReport(
        total_files=len(regular_files),
        text_files=sum(item.kind == "text" for item in files),
        skipped_files=skipped,
        total_uncompressed_bytes=total_bytes,
        files=tuple(files),
        findings=tuple(findings),
    )
