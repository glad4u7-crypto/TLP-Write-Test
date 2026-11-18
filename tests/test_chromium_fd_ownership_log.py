from __future__ import annotations

import pytest

from core.chromium_fd_ownership_log import parse_fd_ownership_diagnostics


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("APAA_FD_OWNERSHIP_DIAG fd=6 operation=acquire previous_owned=1 requested_owned=1 pid=100 tid=101",
         {"fd": 6, "operation": "acquire", "previous_owned": True, "requested_owned": True, "pid": 100, "tid": 101}),
        ("APAA_FD_OWNERSHIP_DIAG fd=10 operation=release previous_owned=0 requested_owned=0 pid=200 tid=201",
         {"fd": 10, "operation": "release", "previous_owned": False, "requested_owned": False, "pid": 200, "tid": 201}),
        ("APAA_FD_OWNERSHIP_DIAG fd=3 operation=close previous_owned=1 requested_owned=0 pid=300 tid=301",
         {"fd": 3, "operation": "close", "previous_owned": True, "requested_owned": False, "pid": 300, "tid": 301}),
    ],
)
def test_parse_valid_fatal_path_record(line, expected):
    assert parse_fd_ownership_diagnostics(line) == [expected]


def test_ignores_malformed_and_impossible_state_transitions():
    stderr = "\n".join([
        "APAA_FD_OWNERSHIP_DIAG fd=x operation=acquire previous_owned=1 requested_owned=1 pid=1 tid=2",
        "APAA_FD_OWNERSHIP_DIAG fd=6 operation=acquire previous_owned=0 requested_owned=1 pid=1 tid=2",
        "APAA_FD_OWNERSHIP_DIAG fd=6 operation=release previous_owned=1 requested_owned=0 pid=1 tid=2",
        "APAA_FD_OWNERSHIP_DIAG fd=6 operation=close previous_owned=0 requested_owned=0 pid=1 tid=2",
        "APAA_FD_OWNERSHIP_DIAG fd=6 operation=acquire previous_owned=1 requested_owned=1 pid=0 tid=2",
    ])
    assert parse_fd_ownership_diagnostics(stderr) == []


def test_bounds_number_of_records():
    line = "APAA_FD_OWNERSHIP_DIAG fd=6 operation=acquire previous_owned=1 requested_owned=1 pid=100 tid=101"
    assert len(parse_fd_ownership_diagnostics("\n".join([line] * 100))) == 64


def test_rejects_non_text_input():
    with pytest.raises(TypeError):
        parse_fd_ownership_diagnostics(None)
