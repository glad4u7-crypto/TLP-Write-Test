import pytest

from core.oci_runtime_compat import (
    OCIRuntimePolicy,
    OCIRuntimeSnapshot,
    assess_oci_runtime,
)


def snapshot(**overrides):
    values = {
        "runtime": "podman",
        "version": "5.4.2",
        "rootless": True,
        "cgroup_version": "2",
        "security_options": ("seccomp", "rootless"),
        "supports_create_inspect_start": True,
        "supports_readonly_rootfs": True,
        "supports_cap_drop_all": True,
        "supports_seccomp_profile": True,
    }
    values.update(overrides)
    return OCIRuntimeSnapshot(**values)


def test_exact_pinned_rootless_podman_contract_passes():
    result = assess_oci_runtime(
        snapshot(),
        OCIRuntimePolicy(runtime="podman", pinned_version="5.4.2"),
    )
    assert result.compatible is True
    assert result.reasons == ("pinned_rootless_runtime_contract_passed",)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"runtime": "docker"}, "runtime_name_mismatch"),
        ({"version": "5.4.1"}, "runtime_version_not_pinned"),
        ({"rootless": False}, "rootless_mode_not_proven"),
        ({"cgroup_version": "1"}, "cgroup_version_mismatch"),
        ({"supports_create_inspect_start": False}, "lifecycle_command_contract_missing"),
        ({"supports_readonly_rootfs": False}, "readonly_rootfs_unsupported"),
        ({"supports_cap_drop_all": False}, "cap_drop_all_unsupported"),
        ({"supports_seccomp_profile": False}, "seccomp_profile_unsupported"),
        ({"security_options": ("rootless",)}, "seccomp_runtime_option_not_reported"),
    ],
)
def test_each_runtime_incompatibility_fails_closed(change, reason):
    result = assess_oci_runtime(
        snapshot(**change),
        OCIRuntimePolicy(runtime="podman", pinned_version="5.4.2"),
    )
    assert result.compatible is False
    assert reason in result.reasons


def test_docker_can_be_assessed_only_against_its_own_exact_pin():
    docker = snapshot(runtime="docker", version="27.5.1")
    result = assess_oci_runtime(
        docker,
        OCIRuntimePolicy(runtime="docker", pinned_version="27.5.1"),
    )
    assert result.compatible is True


def test_missing_exact_version_pin_is_rejected():
    with pytest.raises(ValueError, match="exact pinned"):
        assess_oci_runtime(
            snapshot(),
            OCIRuntimePolicy(runtime="podman", pinned_version=""),
        )
