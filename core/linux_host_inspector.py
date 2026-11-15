"""Rootless, read-only Linux host adapter for P07 signed evidence collection.

Only a fixed nftables read command is executed inside the target network
namespace. No shell, user-supplied command, privilege escalation, or mutation
operation is supported. Runtime identity and PID mapping are supplied by a
separately trusted runtime integration.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import re
import subprocess

from core.browser_nftables import HostCollectionError


class LinuxHostInspectorAdapter:
    """Read effective namespace identity and nftables state for one worker."""

    _MAX_NFT_OUTPUT = 1_048_576
    _COMMAND_TIMEOUT_SECONDS = 5
    _IFACE = re.compile(r"^[A-Za-z0-9_.:-]{1,15}$")
    _IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    _ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "LANG": "C"}

    def __init__(
        self,
        *,
        runtime_attestation_reader: Callable[[], Mapping[str, object]],
        runtime_id: str,
        worker_id: str,
        worker_pid: int,
        proc_root: str = "/proc",
        nsenter_path: str | None = None,
        nft_path: str | None = None,
    ) -> None:
        if not callable(runtime_attestation_reader):
            raise HostCollectionError("A trusted runtime-attestation reader is required.")
        if type(runtime_id) is not str or not self._IDENTIFIER.fullmatch(runtime_id):
            raise HostCollectionError("Runtime identifier is invalid.")
        if type(worker_id) is not str or not self._IDENTIFIER.fullmatch(worker_id):
            raise HostCollectionError("Worker identifier is invalid.")
        if type(worker_pid) is not int or worker_pid <= 1 or worker_pid == os.getpid():
            raise HostCollectionError("A distinct, positive target worker PID is required.")
        if type(proc_root) is not str or not os.path.isabs(proc_root):
            raise HostCollectionError("The procfs root must be an absolute path.")

        self._read_attestation = runtime_attestation_reader
        self._runtime_id = runtime_id
        self._worker_id = worker_id
        self._pid = worker_pid
        self._proc = Path(proc_root)
        self._nsenter = self._resolve_binary(nsenter_path, ("/usr/bin/nsenter", "/bin/nsenter"))
        self._nft = self._resolve_binary(nft_path, ("/usr/sbin/nft", "/sbin/nft"))

    @staticmethod
    def _resolve_binary(explicit: str | None, candidates: tuple[str, ...]) -> str:
        choices = (explicit,) if explicit is not None else candidates
        for candidate in choices:
            if type(candidate) is not str or not os.path.isabs(candidate):
                continue
            resolved = os.path.realpath(candidate)
            if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
                return resolved
        raise HostCollectionError("Required fixed read-only host inspection binary is unavailable.")

    def read_runtime_attestation(self) -> Mapping[str, object]:
        try:
            raw = self._read_attestation()
        except Exception as exc:
            raise HostCollectionError("Trusted runtime attestation read failed.") from exc
        if not isinstance(raw, Mapping):
            raise HostCollectionError("Runtime attestation must be a mapping.")
        return dict(raw)

    def read_network_namespace_identity(self) -> Mapping[str, object]:
        try:
            proc_entry = self._proc / str(self._pid)
            namespace_inode = os.stat(proc_entry / "ns" / "net", follow_symlinks=True).st_ino
            if type(namespace_inode) is not int or namespace_inode <= 0:
                raise HostCollectionError("Target network namespace inode is invalid.")

            net_dev = (proc_entry / "net" / "dev").read_text(encoding="ascii")
            interfaces: list[str] = []
            for line in net_dev.splitlines()[2:]:
                if ":" not in line:
                    continue
                name = line.split(":", 1)[0].strip()
                if name == "lo":
                    continue
                if not self._IFACE.fullmatch(name):
                    raise HostCollectionError("Target namespace contains an invalid interface name.")
                interfaces.append(name)
            if len(interfaces) != 1:
                raise HostCollectionError("Exactly one non-loopback worker interface is required.")
            return {
                "runtime_id": self._runtime_id,
                "worker_id": self._worker_id,
                "inode": namespace_inode,
                "interface": interfaces[0],
            }
        except HostCollectionError:
            raise
        except (OSError, UnicodeError, ValueError) as exc:
            raise HostCollectionError("Target network namespace could not be inspected read-only.") from exc

    def read_nftables_json(self) -> str:
        """Read the effective ruleset inside the target netns; never changes it."""
        command = [
            self._nsenter, "--target", str(self._pid), "--net", "--",
            self._nft, "-j", "list", "ruleset",
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
                close_fds=True,
                timeout=self._COMMAND_TIMEOUT_SECONDS,
                env=dict(self._ENV),
                text=True,
                encoding="utf-8",
                errors="strict",
            )
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise HostCollectionError("Read-only nftables inspection failed.") from exc
        if completed.returncode != 0:
            raise HostCollectionError("Read-only nftables inspection returned a failure status.")
        if (not isinstance(completed.stdout, str) or not completed.stdout
                or len(completed.stdout.encode("utf-8")) > self._MAX_NFT_OUTPUT):
            raise HostCollectionError("nftables snapshot is empty or exceeds the evidence size limit.")
        return completed.stdout
