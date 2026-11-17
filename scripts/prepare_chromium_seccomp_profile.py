from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from core.cgroup_seccomp_provisioner import validate_seccomp_profile


class SeccompProfilePreparationError(ValueError):
    pass


def build_chromium_seccomp_profile(source: dict[str, Any]) -> dict[str, Any]:
    """Derive a default-deny profile allowing chroot syscall, not the capability.

    The kernel still requires CAP_SYS_CHROOT in the caller's current user
    namespace. The worker receives no capabilities in the host user namespace;
    this rule exists only so Chromium's nested unprivileged user-namespace
    sandbox can use chroot after it creates and maps its own user namespace.
    """
    if not isinstance(source, dict) or source.get("defaultAction") != "SCMP_ACT_ERRNO":
        raise SeccompProfilePreparationError("source seccomp profile must retain SCMP_ACT_ERRNO default")
    syscalls = source.get("syscalls")
    if not isinstance(syscalls, list) or not syscalls:
        raise SeccompProfilePreparationError("source seccomp profile has no syscall rules")

    allow_rules = []
    deny_rules = []
    preserved = []
    for rule in syscalls:
        if not isinstance(rule, dict):
            raise SeccompProfilePreparationError("source seccomp rule is malformed")
        names = rule.get("names")
        if not isinstance(names, list):
            raise SeccompProfilePreparationError("source seccomp rule names are malformed")
        if "chroot" not in names:
            preserved.append(copy.deepcopy(rule))
            continue
        if names != ["chroot"] or rule.get("args") != []:
            raise SeccompProfilePreparationError("source chroot rule is not the reviewed exact rule")
        includes = rule.get("includes") or {}
        excludes = rule.get("excludes") or {}
        if (rule.get("action") == "SCMP_ACT_ALLOW"
                and includes.get("caps") == ["CAP_SYS_CHROOT"] and not excludes):
            allow_rules.append(rule)
        elif (rule.get("action") == "SCMP_ACT_ERRNO"
                and excludes.get("caps") == ["CAP_SYS_CHROOT"] and not includes
                and rule.get("errno") == "EPERM"):
            deny_rules.append(rule)
        else:
            raise SeccompProfilePreparationError("source chroot rules differ from the reviewed Podman policy")

    if len(allow_rules) != 1 or len(deny_rules) != 1:
        raise SeccompProfilePreparationError("expected exactly one conditional allow and one conditional deny chroot rule")

    result = copy.deepcopy(source)
    result["syscalls"] = preserved + [{
        "names": ["chroot"],
        "action": "SCMP_ACT_ALLOW",
        "args": [],
        "comment": (
            "APAA: allow chroot syscall for Chromium's nested user-namespace sandbox; "
            "kernel capability checks remain mandatory and host-userns CAP_SYS_CHROOT is not granted"
        ),
    }]
    if result.get("defaultAction") != "SCMP_ACT_ERRNO":
        raise SeccompProfilePreparationError("derived seccomp profile is not default-deny")
    return result


def prepare_profile_file(source_path: str | Path, output_path: str | Path) -> str:
    source = Path(source_path)
    output = Path(output_path)
    if (not source.is_absolute() or source.is_symlink() or not source.is_file()
            or source.resolve(strict=True) != source):
        raise SeccompProfilePreparationError("source seccomp profile must be an absolute regular non-symlink file")
    if (not output.is_absolute() or output.exists() or output.is_symlink()
            or not output.parent.is_dir() or output.parent.is_symlink()):
        raise SeccompProfilePreparationError("output must be a new absolute file in a real existing directory")

    try:
        source_document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SeccompProfilePreparationError("source seccomp profile is unreadable or invalid JSON") from exc
    derived = build_chromium_seccomp_profile(source_document)
    encoded = (json.dumps(derived, sort_keys=True, indent=2) + "\n").encode("utf-8")

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short seccomp profile write")
            view = view[written:]
        os.fsync(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise SeccompProfilePreparationError("derived seccomp profile is not owner-only regular file")
    except Exception:
        os.close(fd)
        output.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)

    try:
        validate_seccomp_profile(output)
        written_document = json.loads(output.read_text(encoding="utf-8"))
        chroot_rules = [
            rule for rule in written_document["syscalls"]
            if "chroot" in rule.get("names", [])
        ]
        if (len(chroot_rules) != 1 or chroot_rules[0].get("action") != "SCMP_ACT_ALLOW"
                or chroot_rules[0].get("args") != []
                or written_document.get("defaultAction") != "SCMP_ACT_ERRNO"):
            raise SeccompProfilePreparationError("derived chroot rule failed post-write verification")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare APAA's narrowly adjusted Chromium userns seccomp profile.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    digest = prepare_profile_file(args.source, args.output)
    print(f"seccomp_profile={args.output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
