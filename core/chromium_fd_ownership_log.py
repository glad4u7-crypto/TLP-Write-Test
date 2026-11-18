"""Parser for structured fatal-path records from diagnostic Chromium builds."""
from __future__ import annotations

import re

_RECORD = re.compile(
    r"APAA_FD_OWNERSHIP_DIAG fd=(\d+) operation=(acquire|release|close) "
    r"previous_owned=([01]) requested_owned=([01]) pid=(\d+) tid=(\d+)"
)
_MAX_RECORDS = 64


def parse_fd_ownership_diagnostics(stderr: str) -> list[dict]:
    """Extract bounded, validated records; ignore malformed/untrusted log lines."""
    if not isinstance(stderr, str):
        raise TypeError("stderr must be text")
    records = []
    for line in stderr.splitlines():
        if "APAA_FD_OWNERSHIP_DIAG" not in line:
            continue
        match = _RECORD.search(line)
        if not match:
            continue
        fd, operation, previous, requested, pid, tid = match.groups()
        record = {
            "fd": int(fd),
            "operation": operation,
            "previous_owned": bool(int(previous)),
            "requested_owned": bool(int(requested)),
            "pid": int(pid),
            "tid": int(tid),
        }
        if record["pid"] <= 0 or record["tid"] <= 0:
            continue
        if operation == "acquire" and not (
            record["previous_owned"] and record["requested_owned"]
        ):
            continue
        if operation == "release" and (
            record["previous_owned"] or record["requested_owned"]
        ):
            continue
        if operation == "close" and not (
            record["previous_owned"] and not record["requested_owned"]
        ):
            continue
        records.append(record)
        if len(records) >= _MAX_RECORDS:
            break
    return records
