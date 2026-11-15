import pytest

from core.identity import AuthenticationRequired
from core.streamlit_auth import OIDCIdentityError, principal_from_oidc_claims


def valid_claims(**overrides):
    claims = {
        "is_logged_in": True,
        "iss": "https://accounts.example.test",
        "sub": "subject-123",
        "iat": 1_000,
        "exp": 2_000,
    }
    claims.update(overrides)
    return claims


def test_oidc_claims_create_principal_from_issuer_and_subject():
    principal = principal_from_oidc_claims(valid_claims(), now=1_500)
    assert principal.subject == "subject-123"
    assert principal.issuer == "https://accounts.example.test"
    assert principal.authenticated is True
    assert principal.roles == ()


@pytest.mark.parametrize(
    "claims",
    [
        None,
        {},
        valid_claims(is_logged_in=False),
        valid_claims(iss=""),
        valid_claims(sub=""),
        valid_claims(exp="2000"),
        valid_claims(iat=True),
        valid_claims(exp=float("nan")),
    ],
)
def test_oidc_adapter_rejects_missing_or_malformed_claims(claims):
    with pytest.raises((AuthenticationRequired, OIDCIdentityError)):
        principal_from_oidc_claims(claims, now=1_500)


def test_oidc_adapter_rejects_expired_identity():
    with pytest.raises(AuthenticationRequired):
        principal_from_oidc_claims(valid_claims(exp=1_000), now=1_500)


def test_oidc_adapter_rejects_future_issued_identity():
    with pytest.raises(AuthenticationRequired):
        principal_from_oidc_claims(valid_claims(iat=2_000), now=1_500)


def test_oidc_adapter_allows_small_clock_skew():
    principal = principal_from_oidc_claims(
        valid_claims(exp=1_450, iat=1_550),
        now=1_500,
        clock_skew_seconds=60,
    )
    assert principal.subject == "subject-123"


@pytest.mark.parametrize("now", [float("nan"), float("inf"), True, "1500"])
def test_oidc_adapter_rejects_invalid_validation_time(now):
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(valid_claims(), now=now)


@pytest.mark.parametrize("clock_skew", [-1, True, 1.5, float("nan")])
def test_oidc_adapter_rejects_invalid_clock_skew(clock_skew):
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(
            valid_claims(), now=1_500, clock_skew_seconds=clock_skew
        )


def test_oidc_adapter_rejects_expiration_exactly_at_clock_skew_boundary():
    # exp == now - skew is expired; the boundary must fail closed.
    with pytest.raises(AuthenticationRequired):
        principal_from_oidc_claims(
            valid_claims(exp=1_440), now=1_500, clock_skew_seconds=60
        )


def test_oidc_adapter_accepts_issued_at_exactly_at_clock_skew_boundary():
    # iat == now + skew is allowed; only values beyond this boundary are future-issued.
    principal = principal_from_oidc_claims(
        valid_claims(iat=1_560), now=1_500, clock_skew_seconds=60
    )
    assert principal.subject == "subject-123"


@pytest.mark.parametrize("claim", ["exp", "iat"])
def test_oidc_adapter_rejects_unrepresentably_large_integer_timestamps(claim):
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(valid_claims(**{claim: 10**1000}), now=1_500)


def test_oidc_adapter_rejects_unrepresentably_large_integer_validation_time():
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(valid_claims(), now=10**1000)


@pytest.mark.parametrize(
    "issuer",
    [
        "http://accounts.example.test",
        "https://",
        "https://user:password@accounts.example.test",
        "https://accounts.example.test/path?tenant=other",
        "https://accounts.example.test/path#fragment",
        "https://accounts.example.test:invalid",
        "https://accounts example.test",
        " https://accounts.example.test",
        "https://accounts.example.test ",
    ],
)
def test_oidc_adapter_rejects_ambiguous_or_non_https_issuer(issuer):
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(valid_claims(iss=issuer), now=1_500)


@pytest.mark.parametrize("subject", ["", "x" * 256, "non-ascii-☃"])
def test_oidc_adapter_rejects_subject_outside_oidc_ascii_length_contract(subject):
    with pytest.raises(OIDCIdentityError):
        principal_from_oidc_claims(valid_claims(sub=subject), now=1_500)


def test_oidc_adapter_preserves_valid_issuer_identifier_exactly():
    issuer = "https://accounts.example.test/tenant/"
    principal = principal_from_oidc_claims(
        valid_claims(iss=issuer), now=1_500
    )
    assert principal.issuer == issuer


def test_oidc_adapter_preserves_subject_exactly_without_normalization():
    # The subject is an opaque identifier; trimming it could merge tenants.
    subject = " subject-123 "
    principal = principal_from_oidc_claims(
        valid_claims(sub=subject), now=1_500
    )
    assert principal.subject == subject
