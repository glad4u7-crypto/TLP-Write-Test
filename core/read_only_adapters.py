"""Bounded read-only adapters for APAA Personal Edition.

The filesystem adapter uses descriptor-relative, no-follow opens and returns
only bounded UTF-8 text. Network providers are injected explicitly; this module
does not create network clients, launch browsers, or register execution actions.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Callable, Protocol

from core.capabilities import (
    CapabilityContractError,
    ReadCapability,
    ReadItem,
    ReadRequest,
    ReadResult,
    _validate_project_relative_path,
)

MAX_FILE_BYTES = 64 * 1024


class ReadOnlyAdapterError(RuntimeError):
    """A read-only adapter could not safely complete its request."""


class ReadOnlyAdapter(Protocol):
    capability: ReadCapability

    def read(self, request: ReadRequest) -> ReadResult: ...


def _open_directory(path: Path) -> int:
    """Open an absolute directory without following any symlink component."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    if not parts or absolute == Path(absolute.anchor):
        raise ReadOnlyAdapterError("A project directory is required.")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open(absolute.anchor, flags)
    try:
        for part in parts[1:]:
            next_fd = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current
    except Exception:
        os.close(current)
        raise


@dataclass(frozen=True)
class ProjectFileReadAdapter:
    """Read one regular UTF-8 file below an Owner-authorized project root."""

    project_root_resolver: Callable[[str], str | os.PathLike[str]]
    max_bytes: int = MAX_FILE_BYTES
    capability: ReadCapability = ReadCapability.FILE_INSPECT

    def __post_init__(self) -> None:
        if not callable(self.project_root_resolver):
            raise TypeError("A trusted project-root resolver is required.")
        if type(self.max_bytes) is not int or not 1 <= self.max_bytes <= MAX_FILE_BYTES:
            raise ValueError("max_bytes must be between 1 and 65536.")

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest) or request.capability is not self.capability:
            raise CapabilityContractError("This adapter accepts only FILE_INSPECT requests.")
        relative = _validate_project_relative_path(request.target)
        root = Path(self.project_root_resolver(request.project_id))
        root_fd = _open_directory(root)
        current_fd = root_fd
        try:
            parts = relative.split("/")
            for part in parts[:-1]:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=current_fd,
                )
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = next_fd
            file_fd = os.open(
                parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
                dir_fd=current_fd,
            )
            try:
                metadata = os.fstat(file_fd)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ReadOnlyAdapterError("Only regular project files can be inspected.")
                if metadata.st_size > self.max_bytes:
                    raise ReadOnlyAdapterError("Project file exceeds the read limit.")
                chunks = []
                remaining = self.max_bytes + 1
                while remaining:
                    chunk = os.read(file_fd, min(8192, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b"".join(chunks)
                if len(raw) > self.max_bytes:
                    raise ReadOnlyAdapterError("Project file exceeds the read limit.")
            finally:
                os.close(file_fd)
        except (OSError, ValueError) as exc:
            if isinstance(exc, ReadOnlyAdapterError):
                raise
            raise ReadOnlyAdapterError("Project file could not be opened safely.") from None
        finally:
            if current_fd != root_fd:
                os.close(current_fd)
            os.close(root_fd)

        try:
            content = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise ReadOnlyAdapterError("Only UTF-8 text files can be inspected.") from None
        return ReadResult(
            capability=self.capability,
            items=(ReadItem(Path(relative).name, relative, content[:2000]),),
            source_label="Owner project files",
            truncated=len(content) > 2000,
        )


@dataclass(frozen=True)
class InjectedReadOnlyProviderAdapter:
    """Wrap an explicitly supplied read-only provider without enabling it by default.

    The injected provider must itself be read-only and return a validated
    ReadResult. No arbitrary handler is exposed through ExecutionGateway.
    """

    capability: ReadCapability
    provider: Callable[[ReadRequest], ReadResult]

    def __post_init__(self) -> None:
        if self.capability not in {
            ReadCapability.WEB_SEARCH,
            ReadCapability.WEB_PAGE_READ,
            ReadCapability.YOUTUBE_SEARCH,
        } or not callable(self.provider):
            raise ValueError("A supported read-only capability and provider are required.")

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest) or request.capability is not self.capability:
            raise CapabilityContractError("Provider received the wrong read capability.")
        result = self.provider(request)
        if not isinstance(result, ReadResult) or result.capability is not self.capability:
            raise ReadOnlyAdapterError("Read-only provider returned an invalid result.")
        if len(result.items) > request.max_results:
            raise ReadOnlyAdapterError("Read-only provider exceeded the requested result bound.")
        return result


class ReadOnlyAdapterRegistry:
    """Explicit allowlist router; it has no write/execute interface."""

    def __init__(self, adapters: tuple[ReadOnlyAdapter, ...] = ()) -> None:
        self._adapters: dict[ReadCapability, ReadOnlyAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ReadOnlyAdapter) -> None:
        capability = getattr(adapter, "capability", None)
        if not isinstance(capability, ReadCapability) or not callable(getattr(adapter, "read", None)):
            raise TypeError("Only typed read-only adapters can be registered.")
        if capability in self._adapters:
            raise ValueError("A read-only adapter is already registered for this capability.")
        self._adapters[capability] = adapter

    def read(self, request: ReadRequest) -> ReadResult:
        if not isinstance(request, ReadRequest):
            raise TypeError("A validated ReadRequest is required.")
        adapter = self._adapters.get(request.capability)
        if adapter is None:
            raise ReadOnlyAdapterError("No adapter is enabled for this read capability.")
        result = adapter.read(request)
        if not isinstance(result, ReadResult) or result.capability is not request.capability:
            raise ReadOnlyAdapterError("Adapter returned an invalid read result.")
        if len(result.items) > request.max_results:
            raise ReadOnlyAdapterError("Adapter exceeded the requested result bound.")
        return result
