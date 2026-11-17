"""Ensure APAA operator preflight tools are importable as a package."""


def test_operator_preflight_scripts_are_importable():
    from scripts import check_apaa_remote_anchor, qualify_apaa_pkcs11_signer

    assert callable(check_apaa_remote_anchor.main)
    assert callable(qualify_apaa_pkcs11_signer.main)
