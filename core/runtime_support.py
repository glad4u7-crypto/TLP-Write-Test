"""Conservative runtime identification for optional browser automation.

This module performs no subprocess calls, package installation, browser download,
or device mutation. Android/Termux is detected and browser launch is blocked
because this repository has no qualified Android Playwright/Chromium evidence.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RuntimeAssessment:
    platform: str
    is_android: bool
    is_termux: bool
    browser_launch_allowed: bool
    reason: str


def assess_runtime(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeAssessment:
    """Classify runtime without executing commands or changing the device."""
    current_platform = sys.platform if platform is None else platform
    env = os.environ if environ is None else environ
    android_markers = any(key in env for key in ("ANDROID_ROOT", "ANDROID_DATA"))
    is_android = current_platform == "android" or android_markers
    prefix = env.get("PREFIX", "").lower()
    termux_marker = "com.termux" in prefix or "com.termux" in env.get("HOME", "").lower()
    is_termux = is_android and termux_marker

    if is_android:
        detail = "Android/Termux browser runtime is not qualified; browser launch is blocked."
        if is_termux:
            detail = "Termux browser runtime is not qualified; browser launch is blocked."
        return RuntimeAssessment(
            platform=current_platform,
            is_android=True,
            is_termux=is_termux,
            browser_launch_allowed=False,
            reason=detail,
        )

    return RuntimeAssessment(
        platform=current_platform,
        is_android=False,
        is_termux=False,
        browser_launch_allowed=True,
        reason="Not detected as Android; host and browser binary still require local validation.",
    )


def require_browser_runtime(*, environ: Mapping[str, str] | None = None) -> RuntimeAssessment:
    """Fail closed on Android until a dedicated compatibility qualification exists."""
    assessment = assess_runtime(environ=environ)
    if not assessment.browser_launch_allowed:
        raise RuntimeError(assessment.reason)
    return assessment
