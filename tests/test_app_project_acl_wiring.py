"""Regression checks for the Streamlit application's project ACL wiring."""

from pathlib import Path


def test_authenticated_project_list_and_detail_use_acl_aware_registry_methods():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert "project_access_control = ProjectAccessControl(project_store)" in source
    assert (
        "project_store, tenant, access_control=project_access_control"
        in source
    )
    assert "return registry.list_projects_for_principal(principal)" in source
    assert "return registry.get_for_principal(project_id, principal)" in source


def test_checkpoint_project_picker_remains_owner_only():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert (
        "project_options = registry.list_projects_for_owner(principal) "
        "if principal is not None else []"
    ) in source
    assert "format_func=lambda value: registry.get(value).name" not in source


def test_acl_registry_is_rebuilt_for_sessions_holding_pre_acl_registry():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert (
        'getattr(st.session_state.get("project_registry"), "_access_control", None) is None'
        in source
    )
