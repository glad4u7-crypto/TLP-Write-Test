"""Android/Termux compatibility contracts for APAA Personal Edition.

This module only assesses support boundaries. It does not launch a server,
install packages, control Chrome, or enable browser-worker dispatch.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AndroidCompatibility:
    android: bool
    termux: bool
    owner_ui_supported: bool
    owner_ui_origin: str
    local_app_host: str
    browser_worker_supported: bool
    browser_worker_reason: str
    physical_device_verified: bool


def assess_android_compatibility(
    *, platform: str | None = None, environ: Mapping[str, str] | None = None
) -> AndroidCompatibility:
    """Return conservative capability claims without probing or mutating a device."""
    current_platform = sys.platform if platform is None else platform
    env = os.environ if environ is None else environ
    android = current_platform == "android" or any(
        key in env for key in ("ANDROID_ROOT", "ANDROID_DATA")
    )
    prefix = env.get("PREFIX", "").lower()
    home = env.get("HOME", "").lower()
    termux = android and ("com.termux" in prefix or "com.termux" in home)

    if android:
        reason = (
            "Android/Termux can host the local Owner interface, but no supported "
            "isolated Chromium worker has been qualified on Android. Browser "
            "execution is disabled; use a separately qualified Linux worker."
        )
        return AndroidCompatibility(
            android=True,
            termux=termux,
            owner_ui_supported=True,
            owner_ui_origin="http://127.0.0.1:<configured-port>",
            local_app_host="127.0.0.1",
            browser_worker_supported=False,
            browser_worker_reason=reason,
            physical_device_verified=False,
        )

    return AndroidCompatibility(
        android=False,
        termux=False,
        owner_ui_supported=True,
        owner_ui_origin="http://127.0.0.1:<configured-port>",
        local_app_host="127.0.0.1",
        browser_worker_supported=False,
        browser_worker_reason=(
            "This assessment does not qualify any browser worker. A separate "
            "host attestation and isolation qualification is required."
        ),
        physical_device_verified=False,
    )


def validate_local_owner_bind(host: str) -> bool:
    """Only loopback bind addresses are accepted for the same-phone Owner UI."""
    return host in {"127.0.0.1", "::1", "localhost"}
