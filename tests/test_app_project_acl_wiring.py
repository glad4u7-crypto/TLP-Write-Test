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



def test_owner_share_controls_require_directory_selection_and_explicit_confirmation():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert "OwnerProjectAccessController(project_access_control)" in source
    assert "list_owner_selectable_identities(" in source
    assert "resolve_owner_selection(" in source
    assert "I confirm this account may view this project's metadata only" in source
    assert "project_access_controller.grant_read(" in source
    assert "project_access_controller.revoke_read(" in source
    assert "I confirm revoking this account's project metadata access" in source
    assert 'oidc_claims.get("name")' in source
    assert 'oidc_claims.get("email")' not in source
