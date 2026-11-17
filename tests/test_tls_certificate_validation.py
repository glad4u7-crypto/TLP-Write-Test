"""Real TLS negative tests for hostname mismatch and expired certificates.

These tests use a local TLS server and a private test CA. They verify that
Python's certificate-validation engine rejects both conditions; they do not
claim to exercise Chromium's own network stack.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _make_certificates(tmp_path, *, expired: bool):
    now = datetime.utcnow()
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "APAA Test Root CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "good.example.test")])
    not_before = now - timedelta(days=10) if expired else now - timedelta(minutes=2)
    not_after = now - timedelta(days=5) if expired else now + timedelta(days=2)
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("good.example.test")]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = tmp_path / "ca.pem"
    cert_path = tmp_path / "server.pem"
    key_path = tmp_path / "server.key"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    return ca_path, cert_path, key_path


def _assert_tls_rejected(tmp_path, *, expired: bool, server_hostname: str, reason: str):
    ca_path, cert_path, key_path = _make_certificates(tmp_path, expired=expired)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    server_errors = []

    def serve_once():
        try:
            raw, _ = listener.accept()
            with raw:
                try:
                    with server_context.wrap_socket(raw, server_side=True) as tls:
                        tls.recv(1)
                except (ssl.SSLError, OSError):
                    # Client rejection is expected; the server may see an alert.
                    pass
        except Exception as exc:
            server_errors.append(exc)
        finally:
            listener.close()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    client_context = ssl.create_default_context(cafile=str(ca_path))
    assert client_context.verify_mode == ssl.CERT_REQUIRED
    assert client_context.check_hostname is True
    client_context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        raw = socket.create_connection(("127.0.0.1", port), timeout=5)
        with raw:
            with pytest.raises(ssl.SSLCertVerificationError, match=reason):
                client_context.wrap_socket(raw, server_hostname=server_hostname)
    finally:
        thread.join(timeout=6)
    assert not thread.is_alive()
    assert server_errors == []


def test_tls_rejects_certificate_hostname_mismatch(tmp_path):
    _assert_tls_rejected(
        tmp_path,
        expired=False,
        server_hostname="wrong.example.test",
        reason="hostname mismatch",
    )


def test_tls_rejects_expired_certificate(tmp_path):
    _assert_tls_rejected(
        tmp_path,
        expired=True,
        server_hostname="good.example.test",
        reason="expired",
    )
