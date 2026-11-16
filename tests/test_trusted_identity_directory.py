import pytest

from core.identity import Principal
from core.project_access import ProjectAccessControl
from core.sqlite_project_store import SQLiteProjectStore
from core.storage import TenantKey
from core.trusted_identity_directory import SQLiteTrustedIdentityDirectory


OWNER = Principal("owner", "https://issuer.example", True)
READER = Principal("reader", "https://issuer.example", True)
OTHER_ISSUER = Principal("reader", "https://other-issuer.example", True)


def setup(tmp_path):
    store = SQLiteProjectStore(tmp_path / "projects.sqlite3")
    project = store.create(
        TenantKey(OWNER.issuer, OWNER.subject),
        name="Private project",
        description="",
    )
    access = ProjectAccessControl(store)
    directory = SQLiteTrustedIdentityDirectory(
        tmp_path / "directory.sqlite3",
        allowed_issuers={OWNER.issuer},
    )
    return project, access, directory


def test_newly_authenticated_identity_is_private_until_explicit_opt_in(tmp_path):
    project, access, directory = setup(tmp_path)
    directory.record_authenticated_principal(READER, provider_display_label="Reader")
    assert directory.list_owner_selectable_identities(
        project.project_id, owner=OWNER, access_control=access
    ) == []

    directory.set_discoverability(READER, discoverable=True)
    identities = directory.list_owner_selectable_identities(
        project.project_id, owner=OWNER, access_control=access
    )
    assert len(identities) == 1
    assert identities[0].display_label == "Reader"


def test_owner_selection_resolves_only_opaque_id_to_authenticated_principal(tmp_path):
    project, access, directory = setup(tmp_path)
    directory.record_authenticated_principal(READER)
    directory.set_discoverability(READER, discoverable=True)
    identity = directory.list_owner_selectable_identities(
        project.project_id, owner=OWNER, access_control=access
    )[0]

    resolved = directory.resolve_owner_selection(
        project.project_id, identity.directory_id, owner=OWNER, access_control=access
    )
    assert resolved == READER


def test_disabling_discoverability_prevents_new_resolution(tmp_path):
    project, access, directory = setup(tmp_path)
    directory.record_authenticated_principal(READER)
    directory.set_discoverability(READER, discoverable=True)
    identity = directory.list_owner_selectable_identities(
        project.project_id, owner=OWNER, access_control=access
    )[0]
    directory.set_discoverability(READER, discoverable=False)

    assert directory.list_owner_selectable_identities(
        project.project_id, owner=OWNER, access_control=access
    ) == []
    with pytest.raises(LookupError):
        directory.resolve_owner_selection(
            project.project_id, identity.directory_id, owner=OWNER, access_control=access
        )


def test_unallowlisted_issuer_and_non_owner_cannot_enroll_or_browse(tmp_path):
    project, access, directory = setup(tmp_path)
    with pytest.raises(PermissionError):
        directory.record_authenticated_principal(OTHER_ISSUER)
    directory.record_authenticated_principal(READER)
    directory.set_discoverability(READER, discoverable=True)

    with pytest.raises(PermissionError):
        directory.list_owner_selectable_identities(
            project.project_id, owner=READER, access_control=access
        )


def test_subject_is_bound_to_exact_issuer_and_directory_ids_are_opaque(tmp_path):
    project, access, directory = setup(tmp_path)
    directory_id = directory.record_authenticated_principal(READER)
    directory.set_discoverability(READER, discoverable=True)
    assert directory_id != READER.subject
    assert directory_id != READER.issuer

    with pytest.raises(LookupError):
        directory.resolve_owner_selection(
            project.project_id, "reader", owner=OWNER, access_control=access
        )


def test_directory_requires_durable_storage_and_explicit_issuer_allowlist(tmp_path):
    with pytest.raises(ValueError):
        SQLiteTrustedIdentityDirectory(":memory:", allowed_issuers={OWNER.issuer})
    with pytest.raises(ValueError):
        SQLiteTrustedIdentityDirectory(tmp_path / "x.sqlite3", allowed_issuers=set())
