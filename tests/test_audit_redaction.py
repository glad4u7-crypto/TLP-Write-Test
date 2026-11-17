import pytest

from core.audit import create_audit_event, redact_sensitive_text


@pytest.mark.parametrize("secret", [
    "password=hunter2",
    "Authorization: Bearer abc.def.ghi",
    "Cookie=sessionid=private-cookie",
    "api_key=sk-live-123456",
    "session_id=opaque-session",
])
def test_audit_redaction_removes_credential_assignments(secret):
    event = create_audit_event("browser.run", False, secret)
    assert "hunter2" not in event.reason
    assert "abc.def.ghi" not in event.reason
    assert "private-cookie" not in event.reason
    assert "sk-live-123456" not in event.reason
    assert "opaque-session" not in event.reason
    assert "[REDACTED]" in event.reason


def test_audit_redaction_hides_url_path_query_and_email():
    value = "failed at https://example.com/private/path?token=secret#fragment user@example.com"
    redacted = redact_sensitive_text(value)
    assert "private/path" not in redacted
    assert "token=secret" not in redacted
    assert "fragment" not in redacted
    assert "user@example.com" not in redacted
    assert "[REDACTED]" in redacted
    assert "[EMAIL REDACTED]" in redacted


def test_audit_redaction_bounds_output_and_rejects_non_string():
    assert len(redact_sensitive_text("x" * 1000)) == 256
    with pytest.raises(TypeError):
        redact_sensitive_text({"token": "secret"})
