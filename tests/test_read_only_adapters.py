from pathlib import Path

import pytest

from core.capabilities import ReadCapability, ReadItem, ReadRequest, ReadResult
from core.read_only_adapters import (
    InjectedReadOnlyProviderAdapter,
    ProjectFileReadAdapter,
    ReadOnlyAdapterError,
    ReadOnlyAdapterRegistry,
)


def test_project_file_adapter_reads_bounded_utf8_text_without_writes(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "notes.txt").write_text("owner-approved text", encoding="utf-8")
    adapter = ProjectFileReadAdapter(lambda project_id: root)
    registry = ReadOnlyAdapterRegistry((adapter,))
    result = registry.read(ReadRequest(
        ReadCapability.FILE_INSPECT, target="notes.txt", project_id="p1"
    ))
    assert result.items[0].excerpt == "owner-approved text"
    assert (root / "notes.txt").read_text(encoding="utf-8") == "owner-approved text"
    assert not hasattr(registry, "write")
    assert not hasattr(registry, "execute")


@pytest.mark.parametrize("target", ["../secret", "/etc/passwd", "link/secret.txt"])
def test_project_file_adapter_rejects_escape_and_symlinks(tmp_path, target):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.write_text("private", encoding="utf-8")
    (root / "link").symlink_to(tmp_path, target_is_directory=True)
    adapter = ProjectFileReadAdapter(lambda _: root)
    with pytest.raises((ValueError, ReadOnlyAdapterError)):
        adapter.read(ReadRequest(ReadCapability.FILE_INSPECT, target=target, project_id="p1"))


def test_project_file_adapter_rejects_oversized_binary_and_special_files(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "large.txt").write_text("x" * 100, encoding="utf-8")
    adapter = ProjectFileReadAdapter(lambda _: root, max_bytes=32)
    with pytest.raises(ReadOnlyAdapterError):
        adapter.read(ReadRequest(ReadCapability.FILE_INSPECT, target="large.txt", project_id="p1"))
    (root / "binary.bin").write_bytes(b"\xff\xfe")
    adapter = ProjectFileReadAdapter(lambda _: root)
    with pytest.raises(ReadOnlyAdapterError):
        adapter.read(ReadRequest(ReadCapability.FILE_INSPECT, target="binary.bin", project_id="p1"))


def test_injected_provider_is_explicit_bounded_and_capability_scoped():
    def provider(request):
        return ReadResult(
            request.capability,
            (ReadItem("Example", "https://example.org"),),
            "test provider",
        )
    adapter = InjectedReadOnlyProviderAdapter(ReadCapability.WEB_SEARCH, provider)
    result = adapter.read(ReadRequest(ReadCapability.WEB_SEARCH, query="example", max_results=1))
    assert len(result.items) == 1
    with pytest.raises(ValueError):
        ReadOnlyAdapterRegistry((adapter, adapter))


def test_provider_cannot_return_wrong_capability_or_exceed_bound():
    adapter = InjectedReadOnlyProviderAdapter(
        ReadCapability.WEB_SEARCH,
        lambda request: ReadResult(
            ReadCapability.WEB_SEARCH,
            tuple(ReadItem("x", "https://example.org") for _ in range(2)),
            "test",
        ),
    )
    with pytest.raises(ReadOnlyAdapterError):
        adapter.read(ReadRequest(ReadCapability.WEB_SEARCH, query="x", max_results=1))


def test_empty_registry_does_not_enable_network_or_execution():
    registry = ReadOnlyAdapterRegistry()
    with pytest.raises(ReadOnlyAdapterError):
        registry.read(ReadRequest(ReadCapability.WEB_SEARCH, query="x"))
    assert not hasattr(registry, "execute")
