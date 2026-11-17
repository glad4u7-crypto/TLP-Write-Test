import pytest

from core.capabilities import (
    CapabilityContractError,
    ReadCapability,
    ReadItem,
    ReadRequest,
    ReadResult,
)


@pytest.mark.parametrize("capability", [ReadCapability.WEB_SEARCH, ReadCapability.YOUTUBE_SEARCH])
def test_search_requests_are_bounded_and_read_only(capability):
    request = ReadRequest(capability, query="find public information", max_results=5)
    assert request.query == "find public information"
    assert request.max_results == 5


def test_web_page_read_requires_credential_free_https_target():
    request = ReadRequest(ReadCapability.WEB_PAGE_READ, target="https://example.org/article")
    assert request.target == "https://example.org/article"


@pytest.mark.parametrize("target", [
    "http://example.org", "https://user:secret@example.org",
    "https://localhost", "https://service.internal",
    "https://127.0.0.1", "https://example.org:8443",
])
def test_web_page_read_rejects_unsafe_targets(target):
    with pytest.raises(CapabilityContractError):
        ReadRequest(ReadCapability.WEB_PAGE_READ, target=target)


def test_file_inspection_is_project_relative_only():
    request = ReadRequest(
        ReadCapability.FILE_INSPECT,
        target="reports/summary.txt",
        project_id="project-1",
    )
    assert request.target == "reports/summary.txt"


@pytest.mark.parametrize("target", [
    "../secret.txt", "/etc/passwd", "C:/private.txt",
    "folder\\secret.txt", "./notes.txt", "folder//notes.txt",
])
def test_file_inspection_rejects_path_escape(target):
    with pytest.raises(CapabilityContractError):
        ReadRequest(ReadCapability.FILE_INSPECT, target=target, project_id="project-1")


@pytest.mark.parametrize("kwargs", [
    {"capability": "web_search", "query": "x"},
    {"capability": ReadCapability.WEB_SEARCH, "query": ""},
    {"capability": ReadCapability.WEB_SEARCH, "query": "x", "target": "https://example.org"},
    {"capability": ReadCapability.WEB_PAGE_READ, "target": "https://example.org", "query": "also search"},
    {"capability": ReadCapability.FILE_INSPECT, "target": "notes.txt"},
    {"capability": ReadCapability.WEB_SEARCH, "query": "x", "max_results": True},
])
def test_malformed_or_ambiguous_requests_fail_closed(kwargs):
    with pytest.raises(CapabilityContractError):
        ReadRequest(**kwargs)


def test_youtube_results_must_use_youtube_hosts():
    result = ReadResult(
        ReadCapability.YOUTUBE_SEARCH,
        (ReadItem("A video", "https://www.youtube.com/watch?v=abc123", "A short description"),),
        "YouTube",
    )
    assert len(result.items) == 1
    with pytest.raises(CapabilityContractError):
        ReadResult(
            ReadCapability.YOUTUBE_SEARCH,
            (ReadItem("Spoofed", "https://attacker.example/video"),),
            "YouTube",
        )


def test_read_results_reject_mutable_lists_and_oversized_items():
    with pytest.raises(CapabilityContractError):
        ReadResult(ReadCapability.WEB_SEARCH, [], "Search")
    with pytest.raises(CapabilityContractError):
        ReadItem("x" * 301, "https://example.org")


def test_file_result_locator_must_remain_project_relative():
    with pytest.raises(CapabilityContractError):
        ReadResult(
            ReadCapability.FILE_INSPECT,
            (ReadItem("Secret", "../secret.txt"),),
            "Project files",
        )


def test_contracts_do_not_register_or_execute_handlers():
    from core.execution import ExecutionGateway

    gateway = ExecutionGateway()
    assert gateway.execute("web_search", {"query": "anything"}).executed is False
