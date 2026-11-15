"""Regression checks for least-privilege and pinned GitHub Actions workflows.

These checks intentionally use only the Python standard library so CI policy
validation does not add a new runtime or test dependency.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "agent-ci.yml",
    ROOT / ".github" / "workflows" / "blank.yml",
)


def test_all_external_workflow_actions_are_pinned_to_full_commit_shas():
    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        # GitHub Actions steps may put `uses` on the list item itself or as a
        # property after `- name`; accept both valid YAML layouts.
        references = re.findall(
            r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", source, re.MULTILINE
        )
        assert references, f"No actions found in {workflow.name}"
        for reference in references:
            action, separator, revision = reference.rpartition("@")
            assert separator and action and re.fullmatch(r"[0-9a-f]{40}", revision), (
                f"{workflow.name} uses an unpinned action: {reference}"
            )


def test_workflows_have_read_only_permissions_and_no_pull_request_target():
    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        assert re.search(
            r"^permissions:\s*\n\s+contents:\s+read\s*$",
            source,
            re.MULTILINE,
        ), f"{workflow.name} must declare contents: read only"
        assert "pull_request_target:" not in source
        assert "write-all" not in source


def test_workflows_bound_runtime_and_cancel_superseded_runs():
    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        assert re.search(r"^concurrency:\s*$", source, re.MULTILINE)
        assert "cancel-in-progress: true" in source
        assert "github.event.pull_request.head.ref || github.ref_name" in source
        # Push and pull_request events for one branch must not cancel each other.
        assert "github.event_name" in source
        assert re.search(r"^\s+timeout-minutes:\s+(15|20)\s*$", source, re.MULTILINE)


def test_dependabot_checks_pip_and_github_actions_weekly_without_auto_merge():
    source = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert 'package-ecosystem: "pip"' in source
    assert 'package-ecosystem: "github-actions"' in source
    assert source.count('interval: "weekly"') == 2
    assert "auto-merge" not in source.lower()
