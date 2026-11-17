"""Browser-level mobile viewport smoke test (emulation, not physical-device proof)."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from core.personal_auth import LocalOwnerAuthStore

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright
expect = playwright_api.expect


ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8501
BASE_URL = f"http://{HOST}:{PORT}"


def _wait_for_server(process: subprocess.Popen, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Streamlit exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(BASE_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Streamlit did not become ready within 45 seconds")


@pytest.fixture(scope="module")
def streamlit_server():
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    personal_data = tempfile.TemporaryDirectory(prefix="apaa-android-smoke-")
    env["APAA_PERSONAL_DATA_DIR"] = personal_data.name
    auth = LocalOwnerAuthStore(Path(personal_data.name) / "owner-auth.sqlite3")
    auth.configure("test-only owner passphrase", "test-only owner passphrase")
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless=true",
            f"--server.address={HOST}",
            f"--server.port={PORT}",
            "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_server(process)
        yield BASE_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        personal_data.cleanup()



def _open_owner_page(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    owner_passphrase = page.get_by_label("Owner passphrase")
    owner_passphrase.wait_for(timeout=30000)
    owner_passphrase.fill("test-only owner passphrase")
    page.get_by_role("button", name="Unlock APAA").click()
    page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=30000)


def test_pixel_sized_viewport_has_no_page_level_horizontal_overflow(streamlit_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        device = playwright.devices["Pixel 7"]
        context = browser.new_context(**device)
        page = context.new_page()
        _open_owner_page(page, streamlit_server)
        page.wait_for_timeout(1200)

        metrics = page.evaluate("""() => ({
          viewport: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          title: document.querySelector('h1')?.textContent || ''
        })""")
        assert metrics["viewport"] > 0
        assert metrics["documentWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["bodyWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["title"], metrics

        context.close()
        browser.close()


def test_mobile_controls_keep_readable_inputs_and_large_primary_targets(streamlit_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(**playwright.devices["Pixel 7"])
        page = context.new_page()
        _open_owner_page(page, streamlit_server)
        page.wait_for_timeout(1200)

        input_sizes = page.locator("input, textarea").evaluate_all(
            "(nodes) => nodes.map(node => parseFloat(getComputedStyle(node).fontSize))"
        )
        assert input_sizes, "Expected the APAA task/project forms to render at least one input"
        assert all(size >= 16 for size in input_sizes), input_sizes

        button_heights = page.locator(
            ".stButton > button, .stFormSubmitButton > button"
        ).evaluate_all(
            "(nodes) => nodes.map(node => node.getBoundingClientRect())."
            "filter(rect => rect.width > 0 && rect.height > 0)."
            "map(rect => rect.height)"
        )
        assert button_heights, "Expected visible APAA primary/action buttons to render"
        assert all(height >= 44 for height in button_heights), button_heights

        context.close()
        browser.close()



def test_android_user_can_prepare_and_review_plan_without_execution(streamlit_server):
    """Exercise the primary phone workflow; planning must remain non-executing."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(**playwright.devices["Pixel 7"])
        page = context.new_page()
        _open_owner_page(page, streamlit_server)
        page.get_by_label("Describe a task").wait_for(timeout=30000)
        task_input = page.get_by_label("Describe a task")
        task_input.fill(
            "Review a Python repository and suggest a safe implementation plan."
        )
        # Streamlit commits text-area edits on blur; wait for its rerun to
        # update the server-derived disabled state before interacting.
        task_input.press("Tab")
        prepare_button = page.get_by_role("button", name="Prepare structured plan")
        expect(prepare_button).to_be_enabled(timeout=15000)
        prepare_button.click()
        page.get_by_text("Structured plan review").wait_for(timeout=30000)
        page.get_by_text("READY · Reviewable plan prepared. Nothing has been executed.").wait_for()

        action_buttons = page.get_by_role("button").all_text_contents()
        assert not any(
            any(token in label.casefold() for token in ("execute", "run task", "approve action", "auto-run"))
            for label in action_buttons
        ), action_buttons

        metrics = page.evaluate("""() => ({
          viewport: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth
        })""")
        assert metrics["documentWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["bodyWidth"] <= metrics["viewport"] + 2, metrics

        context.close()
        browser.close()

@pytest.mark.parametrize(
    ("width", "height"),
    [
        (320, 720),
        (360, 800),
        (393, 852),
        (412, 915),
        (915, 412),  # landscape handset viewport
    ],
)
def test_android_responsive_viewport_matrix_has_usable_controls(
    streamlit_server, width, height
):
    """Check common narrow Android widths and landscape without claiming device proof."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        _open_owner_page(page, streamlit_server)
        page.get_by_label("Describe a task").wait_for(timeout=30000)
        page.wait_for_timeout(800)

        metrics = page.evaluate("""() => ({
          viewport: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          inputSizes: Array.from(document.querySelectorAll("input, textarea"))
            .map(node => parseFloat(getComputedStyle(node).fontSize)),
          primaryTargets: Array.from(document.querySelectorAll(
            ".stButton > button, .stFormSubmitButton > button"
          )).map(node => {
            const rect = node.getBoundingClientRect();
            return {width: rect.width, height: rect.height};
          }).filter(rect => rect.width > 0 && rect.height > 0)
        })""")
        assert metrics["documentWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["bodyWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["inputSizes"], metrics
        assert all(size >= 16 for size in metrics["inputSizes"]), metrics
        assert metrics["primaryTargets"], metrics
        assert all(
            target["width"] >= 44 and target["height"] >= 44
            for target in metrics["primaryTargets"]
        ), metrics

        context.close()
        browser.close()
