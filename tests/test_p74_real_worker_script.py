from __future__ import annotations

from scripts import p74_real_worker_chromium_e2e as qualification


def test_real_host_qualification_is_opt_in_and_does_not_touch_host(monkeypatch):
    monkeypatch.delenv("APAA_P74_REAL_HOST", raising=False)
    assert qualification.main() == 2


def test_real_host_qualification_rejects_unsafe_worker_id(monkeypatch):
    monkeypatch.setenv("APAA_P74_REAL_HOST", "1")
    monkeypatch.setenv("APAA_P74_WORKER_ID", "../host")
    assert qualification.main() == 2
