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
        "project_options = registry.list_projects_for_owner(checkpoint_principal)"
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


def test_authenticated_deployment_fails_closed_for_non_owner_or_missing_owner():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert "from core.global_owner import GlobalOwnerConfigurationError, is_global_owner" in source
    assert "if auth_required:" in source
    assert "if global_owner_config_invalid or global_owner_config is None:" in source
    assert "if not is_global_owner(principal, global_owner_config):" in source
    assert "This APAA instance is private and is available only to its configured owner." in source
    assert source.index("if not is_global_owner(principal, global_owner_config):") < source.index(
        "st.header(\"Project Manager\")"
    )
