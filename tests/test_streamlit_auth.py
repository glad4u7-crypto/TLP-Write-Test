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
