"""Chromium's real TLS stack: reject an untrusted HTTPS certificate.

This is a browser-process integration test, not a Python ssl-only test. A tiny
CONNECT proxy is used so the browser follows the same proxy-only egress model.
"""
from __future__ import annotations

import socket
import ssl
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
        self.wfile.write(b"unexpected TLS success")

    def log_message(self, *_args):
        pass


class _ConnectProxy:
    def __init__(self):
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

    @staticmethod
    def _tunnel(client):
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
            # This test proxy is deliberately constrained to the local TLS
            # fixture; it cannot become a general-purpose open proxy.
            if host not in ("127.0.0.1", "localhost"):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            upstream = socket.create_connection((host, int(port_text)), timeout=5)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            sockets = (client, upstream)
            client.settimeout(None)
            upstream.settimeout(None)
            while True:
                readable, _, _ = __import__("select").select(sockets, [], [], 5)
                if not readable:
                    continue
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except (OSError, ValueError):
            pass
        finally:
            try:
                client.close()
            except OSError:
                pass
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass

    def close(self):
        self.stop.set()
        self.server.close()
        self.thread.join(timeout=2)


def _self_signed_tls_server(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(__import__("datetime").datetime.utcnow())
        .not_valid_after(__import__("datetime").datetime.utcnow().replace(year=__import__("datetime").datetime.utcnow().year + 1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "chromium-cert.pem", tmp_path / "chromium-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    server = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.chromium
def test_real_chromium_rejects_untrusted_certificate_through_proxy(tmp_path):
    try:
        playwright = sync_playwright().start()
    except PlaywrightError as exc:
        pytest.fail(f"Playwright runtime is required for Chromium integration: {exc}")
    server, server_thread = _self_signed_tls_server(tmp_path)
    proxy = _ConnectProxy()
    browser = None
    try:
        browser = playwright.chromium.launch(
            headless=True,
            chromium_sandbox=True,
            proxy={"server": f"http://127.0.0.1:{proxy.port}"},
            args=["--proxy-bypass-list=<-loopback>", "--disable-background-networking",
                  "--disable-component-update", "--disable-sync"],
        )
        context = browser.new_context(
            ignore_https_errors=False,
            accept_downloads=False,
            service_workers="block",
        )
        page = context.new_page()
        with pytest.raises(PlaywrightError, match="ERR_CERT_AUTHORITY_INVALID"):
            page.goto(f"https://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded", timeout=10000)
        context.close()
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
        proxy.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
