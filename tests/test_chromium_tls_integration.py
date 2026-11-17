"""Real Chromium TLS acceptance tests (not Python ssl-only checks).

The tests launch a disposable headless Chromium process through a constrained
CONNECT proxy. A private test CA is installed into Chromium's isolated NSS
trust database; no certificate-ignore switch is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import select
import shutil
import socket
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import Error as PlaywrightError, sync_playwright


class _QuietHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"chromium TLS accepted")

    def log_message(self, *_args):
        pass


class _ConnectProxy:
    """A local-only CONNECT proxy; it cannot be used as a general open proxy."""
    def __init__(self, upstream_port: int):
        self.upstream_port = upstream_port
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        self.port = self.server.getsockname()[1]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        self.server.settimeout(0.2)
        while not self.stop.is_set():
            try:
                client, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._tunnel, args=(client,), daemon=True).start()

    def _tunnel(self, client):
        upstream = None
        try:
            client.settimeout(5)
            request = b""
            while b"\r\n\r\n" not in request and len(request) < 8192:
                chunk = client.recv(1024)
                if not chunk:
                    return
                request += chunk
            first = request.split(b"\r\n", 1)[0].decode("ascii", "replace")
            parts = first.split()
            if len(parts) != 3 or parts[0] != "CONNECT":
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            host, port_text = parts[1].rsplit(":", 1)
            if host not in ("localhost", "127.0.0.1", "wrong.test") or int(port_text) != self.upstream_port:
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            upstream = socket.create_connection(("127.0.0.1", self.upstream_port), timeout=5)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            client.settimeout(None)
            upstream.settimeout(None)
            sockets = (client, upstream)
            while True:
                readable, _, _ = select.select(sockets, [], [], 5)
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except (OSError, ValueError):
            pass
        finally:
            client.close()
            if upstream is not None:
                upstream.close()

    def close(self):
        self.stop.set()
        self.server.close()
        self.thread.join(timeout=2)


def _write_certificates(tmp_path: Path, *, leaf_name: str, expired: bool):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # cryptography builder expects naive UTC
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "APAA Chromium Test Root")])
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False, key_agreement=False,
            key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, leaf_name)])
    not_before = now - timedelta(days=10) if expired else now - timedelta(minutes=5)
    not_after = now - timedelta(days=1) if expired else now + timedelta(days=10)
    leaf = (
        x509.CertificateBuilder().subject_name(subject).issuer_name(ca_name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(leaf_name)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path, cert_path, key_path = (tmp_path / "test-ca.pem", tmp_path / "server-cert.pem", tmp_path / "server-key.pem")
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return ca_path, cert_path, key_path


def _start_tls_server(cert_path: Path, key_path: Path):
    server = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _browser_with_test_ca(tmp_path: Path, ca_path: Path, proxy_port: int, monkeypatch):
    certutil = shutil.which("certutil")
    if not certutil:
        pytest.fail("NSS certutil is required to install the test CA into Chromium's isolated trust database")
    home = tmp_path / "chromium-home"
    nssdb = home / ".pki" / "nssdb"
    nssdb.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    subprocess.run([certutil, "-N", "-d", f"sql:{nssdb}", "--empty-password"],
                   check=True, capture_output=True, text=True)
    subprocess.run([certutil, "-A", "-d", f"sql:{nssdb}", "-n", "APAA Test Root",
                    "-t", "C,,", "-i", str(ca_path)],
                   check=True, capture_output=True, text=True)
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        str(tmp_path / "chromium-profile"), headless=True, chromium_sandbox=False,
        proxy={"server": f"http://127.0.0.1:{proxy_port}"},
        ignore_https_errors=False, accept_downloads=False, service_workers="block",
        args=["--proxy-bypass-list=<-loopback>", "--disable-background-networking",
              "--disable-component-update", "--disable-sync"],
    )
    return playwright, context


def _run_case(tmp_path, monkeypatch, *, cert_name: str, expired: bool, url_host: str):
    ca_path, cert_path, key_path = _write_certificates(
        tmp_path, leaf_name=cert_name, expired=expired
    )
    server, server_thread = _start_tls_server(cert_path, key_path)
    proxy = _ConnectProxy(server.server_port)
    playwright = context = None
    try:
        playwright, context = _browser_with_test_ca(tmp_path, ca_path, proxy.port, monkeypatch)
        page = context.new_page()
        return page, f"https://{url_host}:{server.server_port}/", context, playwright, proxy, server, server_thread
    except Exception:
        try:
            _cleanup(context, playwright, proxy, server, server_thread)
        except Exception:
            # Preserve the original setup failure; cleanup is best-effort here.
            pass
        raise


def _cleanup(context, playwright, proxy, server, server_thread):
    """Attempt every teardown operation, even if an earlier one fails."""
    errors = []
    for cleanup in (
        context.close,
        playwright.stop,
        proxy.close,
        server.shutdown,
        server.server_close,
        lambda: server_thread.join(timeout=2),
    ):
        try:
            cleanup()
        except Exception as exc:
            errors.append(exc)
    if errors:
        raise errors[0]


def test_chromium_accepts_certificate_signed_by_trusted_test_ca(tmp_path, monkeypatch):
    page, url, context, playwright, proxy, server, server_thread = _run_case(
        tmp_path, monkeypatch, cert_name="localhost", expired=False, url_host="localhost"
    )
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=10000)
        assert response is not None and response.status == 200
        assert page.locator("body").inner_text() == "chromium TLS accepted"
    finally:
        _cleanup(context, playwright, proxy, server, server_thread)


def test_chromium_rejects_trusted_certificate_with_hostname_mismatch(tmp_path, monkeypatch):
    page, url, context, playwright, proxy, server, server_thread = _run_case(
        tmp_path, monkeypatch, cert_name="localhost", expired=False, url_host="wrong.test"
    )
    try:
        with pytest.raises(PlaywrightError, match="ERR_CERT_COMMON_NAME_INVALID"):
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
    finally:
        _cleanup(context, playwright, proxy, server, server_thread)


def test_chromium_rejects_expired_certificate_signed_by_trusted_test_ca(tmp_path, monkeypatch):
    page, url, context, playwright, proxy, server, server_thread = _run_case(
        tmp_path, monkeypatch, cert_name="localhost", expired=True, url_host="localhost"
    )
    try:
        with pytest.raises(PlaywrightError, match="ERR_CERT_DATE_INVALID"):
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
    finally:
        _cleanup(context, playwright, proxy, server, server_thread)
