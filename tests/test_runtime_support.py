import pytest

from core.runtime_support import assess_runtime, require_browser_runtime


def test_android_environment_is_detected_and_browser_launch_denied():
    result = assess_runtime(
        platform="linux",
        environ={"ANDROID_ROOT": "/system", "ANDROID_DATA": "/data"},
    )
    assert result.is_android is True
    assert result.browser_launch_allowed is False
    assert "not qualified" in result.reason


def test_termux_environment_is_detected():
    result = assess_runtime(
        platform="linux",
        environ={
            "ANDROID_ROOT": "/system",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
        },
    )
    assert result.is_android is True
    assert result.is_termux is True
    assert result.browser_launch_allowed is False


def test_non_android_host_is_not_mislabelled_as_android():
    result = assess_runtime(platform="linux", environ={"HOME": "/home/test"})
    assert result.is_android is False
    assert result.browser_launch_allowed is True
    assert "require local validation" in result.reason


def test_require_browser_runtime_fails_closed_for_android():
    with pytest.raises(RuntimeError, match="Android"):
        require_browser_runtime(environ={"ANDROID_DATA": "/data"})
