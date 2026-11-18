import json
import stat

import pytest

from scripts.prepare_chromium_seccomp_profile import (
    SeccompProfilePreparationError,
    build_chromium_seccomp_profile,
    prepare_profile_file,
)


def source_profile():
    return {
        "defaultAction": "SCMP_ACT_ERRNO",
        "architectures": ["SCMP_ARCH_X86_64"],
        "syscalls": [
            {"names": ["read", "write"], "action": "SCMP_ACT_ALLOW", "args": []},
            {
                "names": ["chroot"], "action": "SCMP_ACT_ALLOW", "args": [],
                "includes": {"caps": ["CAP_SYS_CHROOT"]},
            },
            {
                "names": ["chroot"], "action": "SCMP_ACT_ERRNO", "errno": "EPERM",
                "args": [], "excludes": {"caps": ["CAP_SYS_CHROOT"]},
            },
        ],
    }


def test_profile_allows_chroot_syscall_but_keeps_kernel_capability_gate():
    source = source_profile()
    derived = build_chromium_seccomp_profile(source)
    assert derived["defaultAction"] == "SCMP_ACT_ERRNO"
    assert [rule for rule in derived["syscalls"] if rule["names"] == ["read", "write"]] == [
        source["syscalls"][0]
    ]
    chroot = [rule for rule in derived["syscalls"] if "chroot" in rule["names"]]
    assert len(chroot) == 1
    assert chroot[0]["action"] == "SCMP_ACT_ALLOW"
    assert chroot[0]["args"] == []
    assert "includes" not in chroot[0] and "excludes" not in chroot[0]
    assert "comment" not in chroot[0]
    assert source == source_profile()


def test_profile_rejects_unexpected_default_action():
    source = source_profile()
    source["defaultAction"] = "SCMP_ACT_ALLOW"
    with pytest.raises(SeccompProfilePreparationError, match="SCMP_ACT_ERRNO"):
        build_chromium_seccomp_profile(source)


def test_profile_rejects_missing_or_changed_conditional_chroot_rules():
    source = source_profile()
    source["syscalls"] = source["syscalls"][:1]
    with pytest.raises(SeccompProfilePreparationError, match="exactly one conditional"):
        build_chromium_seccomp_profile(source)

    source = source_profile()
    source["syscalls"][1]["args"] = [{"index": 0, "value": 0}]
    with pytest.raises(SeccompProfilePreparationError, match="exact rule"):
        build_chromium_seccomp_profile(source)


def test_profile_file_is_owner_only_and_validated(tmp_path):
    source = tmp_path / "default-seccomp.json"
    output = tmp_path / "apaa-chromium-seccomp.json"
    source.write_text(json.dumps(source_profile()), encoding="utf-8")
    digest = prepare_profile_file(source, output)
    assert len(digest) == 64
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["defaultAction"] == "SCMP_ACT_ERRNO"
    assert len([rule for rule in written["syscalls"] if "chroot" in rule["names"]]) == 1


def test_profile_file_rejects_symlink_source_and_existing_output(tmp_path):
    source = tmp_path / "default-seccomp.json"
    source.write_text(json.dumps(source_profile()), encoding="utf-8")
    source_link = tmp_path / "source-link.json"
    source_link.symlink_to(source)
    with pytest.raises(SeccompProfilePreparationError, match="non-symlink"):
        prepare_profile_file(source_link, tmp_path / "output.json")

    output = tmp_path / "output.json"
    output.symlink_to(source)
    with pytest.raises(SeccompProfilePreparationError, match="new absolute file"):
        prepare_profile_file(source, output)
