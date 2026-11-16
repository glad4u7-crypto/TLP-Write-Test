"""Browser-level mobile viewport smoke test (emulation, not physical-device proof)."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright


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


def test_pixel_sized_viewport_has_no_page_level_horizontal_overflow(streamlit_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        device = playwright.devices["Pixel 7"]
        context = browser.new_context(**device)
        page = context.new_page()
        page.goto(streamlit_server, wait_until="domcontentloaded", timeout=30000)
        page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=30000)
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
        page.goto(streamlit_server, wait_until="domcontentloaded", timeout=30000)
        page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=30000)
        page.wait_for_timeout(1200)

        input_sizes = page.locator("input, textarea").evaluate_all(
            "(nodes) => nodes.map(node => parseFloat(getComputedStyle(node).fontSize))"
        )
        assert input_sizes, "Expected the APAA task/project forms to render at least one input"
        assert all(size >= 16 for size in input_sizes), input_sizes

        button_heights = page.locator(
            ".stButton > button, .stFormSubmitButton > button"
        ).evaluate_all(
            "(nodes) => nodes.map(node => node.getBoundingClientRect().height)"
        )
        assert button_heights, "Expected APAA primary/action buttons to render"
        assert all(height >= 44 for height in button_heights), button_heights

        context.close()
        browser.close()



def test_android_user_can_prepare_and_review_plan_without_execution(streamlit_server):
    """Exercise the primary phone workflow; planning must remain non-executing."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(**playwright.devices["Pixel 7"])
        page = context.new_page()
        page.goto(streamlit_server, wait_until="domcontentloaded", timeout=30000)
        page.get_by_label("Describe a task").wait_for(timeout=30000)
        page.get_by_label("Describe a task").fill(
            "Review a Python repository and suggest a safe implementation plan."
        )
        page.get_by_role("button", name="Prepare structured plan").click()
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
