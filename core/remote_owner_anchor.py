"""Mutual-TLS client adapter for an independently operated monotonic anchor.

This is a client, not an anchor server. The remote service must implement the
documented atomic CAS API and independently guarantee durable monotonic history
across backup/restore, deletion/recreation and administrative recovery.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import stat
import hmac
from urllib.parse import quote, urlsplit

from core.offline_owner_recovery import AnchorState

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESPONSE = 65_536
_MAX_REQUEST = 16_384


class RemoteAnchorError(RuntimeError):
    """Remote anchor is unavailable, unauthenticated, malformed or inconsistent."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RemoteAnchorError("Remote anchor returned duplicate JSON fields.")
        result[key] = value
    return result


def _state(raw: object) -> AnchorState:
    if not isinstance(raw, dict) or set(raw) != {"revision", "generation", "change_id"}:
        raise RemoteAnchorError("Remote anchor state schema is invalid.")
    revision, generation, change_id = raw["revision"], raw["generation"], raw["change_id"]
    if (type(revision) is not int or revision < 0
            or (generation is not None and (type(generation) is not str or not _DIGEST.fullmatch(generation)))
            or (change_id is not None and (type(change_id) is not str or not _ID.fullmatch(change_id)))
            or (revision == 0 and (generation is not None or change_id is not None))
            or (revision > 0 and change_id is None)):
        raise RemoteAnchorError("Remote anchor state values are invalid.")
    return AnchorState(revision, generation, change_id)


def _state_json(value: AnchorState) -> dict:
    if not isinstance(value, AnchorState):
        raise RemoteAnchorError("Anchor transition state type is invalid.")
    return {"revision": value.revision, "generation": value.generation, "change_id": value.change_id}


def _secure_file(path: str | os.PathLike[str], *, private: bool) -> str:
    p = Path(path).expanduser()
    try:
        info = p.lstat()
    except OSError:
        raise RemoteAnchorError("TLS credential file is unavailable.") from None
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise RemoteAnchorError("TLS credential must be a regular non-symlink file.")
    if private and os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
        raise RemoteAnchorError("TLS private key permissions must be 0600 or stricter.")
    return str(p.resolve(strict=True))


class HTTPSMonotonicAnchor:
    """mTLS adapter implementing both owner-anchor and inspector-sequence APIs.

    API contract:
      GET  /v1/anchors/{id} -> {"schema_version":1,"state":{...}}
      POST /v1/anchors/{id}/compare-and-advance
           {"schema_version":1,"expected":{...},"target":{...}}
           -> 200 {"schema_version":1,"advanced":true,"state":{target}}
              or 409 {"schema_version":1,"advanced":false,"state":{current}}
      GET  /v1/sequences/{issuer} -> {"schema_version":1,"sequence":N}
      POST /v1/sequences/{issuer}/compare-and-advance
           {"schema_version":1,"expected_current":N,"new_sequence":N+1}
           -> 200 {"schema_version":1,"advanced":true,"sequence":N+1}
              or 409 {"schema_version":1,"advanced":false,"sequence":current}

    The service MUST perform a single atomic conditional write and persist it
    before acknowledging. Redirects, non-HTTPS, malformed responses, stale
    results, authentication failures and ambiguous outcomes fail closed.
    """

    def __init__(
        self, *, endpoint: str, ca_file: str, client_cert: str,
        client_key: str, anchor_id: str, timeout_seconds: float = 5.0,
        server_cert_sha256: str | None = None, connection_factory=None,
        ssl_context_factory=None,
    ) -> None:
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise RemoteAnchorError("Anchor endpoint must be a credential-free HTTPS URL.")
        if type(anchor_id) is not str or not _ID.fullmatch(anchor_id):
            raise RemoteAnchorError("Anchor identifier is invalid.")
        if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 30:
            raise RemoteAnchorError("Anchor network timeout must be between 1 and 30 seconds.")
        if server_cert_sha256 is not None and (
            type(server_cert_sha256) is not str or not _DIGEST.fullmatch(server_cert_sha256)
        ):
            raise RemoteAnchorError("Pinned server certificate SHA-256 must be lowercase hex.")
        self._host, self._port = parsed.hostname, parsed.port or 443
        self._prefix = parsed.path.rstrip("/")
        self._anchor_id = anchor_id
        self._timeout = float(timeout_seconds)
        self._fingerprint = server_cert_sha256
        self._factory = connection_factory or http.client.HTTPSConnection
        try:
            ca = _secure_file(ca_file, private=False)
            cert = _secure_file(client_cert, private=False)
            key = _secure_file(client_key, private=True)
            context = (
                ssl_context_factory(ca) if ssl_context_factory is not None
                else ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca)
            )
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_cert_chain(certfile=cert, keyfile=key)
            self._context = context
        except RemoteAnchorError:
            raise
        except Exception:
            raise RemoteAnchorError("mTLS client identity or CA configuration is invalid.") from None

    def _request(self, method: str, route: str, payload: dict | None = None):
        raw = None if payload is None else json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if raw is not None and len(raw) > _MAX_REQUEST:
            raise RemoteAnchorError("Anchor request exceeds the size limit.")
        connection = None
        try:
            connection = self._factory(
                self._host, self._port, context=self._context, timeout=self._timeout,
            )
            headers = {"Accept": "application/json", "Connection": "close"}
            if raw is not None:
                headers["Content-Type"] = "application/json"
            connection.request(method, self._prefix + route, body=raw, headers=headers)
            response = connection.getresponse()
            body = response.read(_MAX_RESPONSE + 1)
            if len(body) > _MAX_RESPONSE:
                raise RemoteAnchorError("Anchor response exceeds the size limit.")
            if self._fingerprint is not None:
                sock = getattr(connection, "sock", None)
                cert = sock.getpeercert(binary_form=True) if sock is not None else None
                if not cert or not hmac.compare_digest(hashlib.sha256(cert).hexdigest(), self._fingerprint):
                    raise RemoteAnchorError("Anchor TLS certificate fingerprint mismatch.")
            if response.status not in (200, 409):
                # No redirects, implicit bootstrap, or optimistic interpretation.
                raise RemoteAnchorError(f"Anchor service rejected the request (HTTP {response.status}).")
            try:
                document = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
            except (UnicodeError, json.JSONDecodeError):
                raise RemoteAnchorError("Anchor response is not valid UTF-8 JSON.") from None
            if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
                    or document.get("schema_version") != 1):
                raise RemoteAnchorError("Anchor response schema version is invalid.")
            return response.status, document
        except RemoteAnchorError:
            raise
        except Exception:
            raise RemoteAnchorError("Anchor transport failed; outcome may be unknown, re-read before retry.") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def read(self) -> AnchorState:
        status, document = self._request(
            "GET", f"/v1/anchors/{quote(self._anchor_id, safe='')}",
        )
        if status != 200 or set(document) != {"schema_version", "state"}:
            raise RemoteAnchorError("Anchor read response is not authoritative.")
        return _state(document["state"])

    def compare_and_advance(self, *, expected: AnchorState, target: AnchorState) -> bool:
        expected_state, target_state = _state_json(_state(_state_json(expected))), _state_json(_state(_state_json(target)))
        if target.revision != expected.revision + 1 or target.change_id is None:
            return False
        status, document = self._request(
            "POST", f"/v1/anchors/{quote(self._anchor_id, safe='')}/compare-and-advance",
            {"schema_version": 1, "expected": expected_state, "target": target_state},
        )
        if set(document) != {"schema_version", "advanced", "state"} or type(document["advanced"]) is not bool:
            raise RemoteAnchorError("Anchor CAS response schema is invalid.")
        returned = _state(document["state"])
        if status == 409:
            if document["advanced"] is not False:
                raise RemoteAnchorError("Anchor conflict response is inconsistent.")
            return False
        if document["advanced"] is not True or returned != target:
            raise RemoteAnchorError("Anchor did not durably confirm the exact target state.")
        return True

    def read_sequence(self, issuer_key_id: str) -> int:
        if type(issuer_key_id) is not str or not _ID.fullmatch(issuer_key_id):
            raise RemoteAnchorError("Trust issuer identifier is invalid.")
        status, document = self._request(
            "GET", f"/v1/sequences/{quote(issuer_key_id, safe='')}",
        )
        if status != 200 or set(document) != {"schema_version", "sequence"}:
            raise RemoteAnchorError("Sequence read response is not authoritative.")
        value = document["sequence"]
        if type(value) is not int or value < 0:
            raise RemoteAnchorError("Sequence anchor value is invalid.")
        return value

    def advance_sequence(
        self, issuer_key_id: str, *, expected_current: int, new_sequence: int,
    ) -> bool:
        if (type(issuer_key_id) is not str or not _ID.fullmatch(issuer_key_id)
                or type(expected_current) is not int or expected_current < 0
                or type(new_sequence) is not int or new_sequence != expected_current + 1):
            return False
        status, document = self._request(
            "POST", f"/v1/sequences/{quote(issuer_key_id, safe='')}/compare-and-advance",
            {"schema_version": 1, "expected_current": expected_current, "new_sequence": new_sequence},
        )
        if set(document) != {"schema_version", "advanced", "sequence"} or type(document["advanced"]) is not bool:
            raise RemoteAnchorError("Sequence CAS response schema is invalid.")
        current = document["sequence"]
        if type(current) is not int or current < 0:
            raise RemoteAnchorError("Sequence CAS returned an invalid value.")
        if status == 409:
            if document["advanced"] is not False:
                raise RemoteAnchorError("Sequence conflict response is inconsistent.")
            return False
        if document["advanced"] is not True or current != new_sequence:
            raise RemoteAnchorError("Sequence CAS did not confirm the exact target.")
        return True
