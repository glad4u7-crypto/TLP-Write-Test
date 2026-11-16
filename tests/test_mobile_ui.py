from core.mobile_ui import MOBILE_FIRST_CSS


def test_mobile_first_styles_include_android_touch_and_viewport_support():
    assert "@media (max-width: 768px)" in MOBILE_FIRST_CSS
    assert "min-height: 44px" in MOBILE_FIRST_CSS
    assert "font-size: 16px !important" in MOBILE_FIRST_CSS
    assert "overflow-x: auto" in MOBILE_FIRST_CSS
    assert "max-width: 100%" in MOBILE_FIRST_CSS


def test_mobile_styles_do_not_enable_automatic_execution_or_external_providers():
    lowered = MOBILE_FIRST_CSS.lower()
    assert "auto_run" not in lowered
    assert "paid_api" not in lowered
    assert "execute_task" not in lowered
