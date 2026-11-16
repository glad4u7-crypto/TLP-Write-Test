"""Read-only host-side Docker/Podman qualification preflight.

Run with: python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2

This command never creates, starts, stops, or removes containers and never
changes daemon, network, firewall, or host configuration.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from collections.abc import Sequence

from core.oci_runtime_probe import probe_oci_runtime
from core.oci_worker_executor import CommandRunner, subprocess_command_runner


def main(argv: Sequence[str] | None = None, *, runner: CommandRunner | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only rootless OCI runtime qualification preflight")
    parser.add_argument("--runtime", choices=("docker", "podman"), required=True)
    parser.add_argument("--pinned-version", required=True)
    args = parser.parse_args(argv)

    try:
        assessment = probe_oci_runtime(
            args.runtime,
            runner=runner or subprocess_command_runner,
            pinned_version=args.pinned_version,
        )
    except Exception as exc:
        print(json.dumps({
            "qualified": False,
            "runtime": args.runtime,
            "pinned_version": args.pinned_version,
            "error": type(exc).__name__,
            "reason": "read_only_runtime_probe_failed_closed",
        }, sort_keys=True))
        return 2

    print(json.dumps({
        "qualified": assessment.compatible,
        **asdict(assessment),
    }, sort_keys=True))
    return 0 if assessment.compatible else 2


if __name__ == "__main__":
    raise SystemExit(main())
