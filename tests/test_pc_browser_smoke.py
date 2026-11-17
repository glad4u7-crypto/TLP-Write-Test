"""Desktop browser viewport smoke test; emulation is not physical-device proof."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright
expect = playwright_api.expect

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8502
BASE_URL = f"http://{HOST}:{PORT}"


@pytest.fixture(scope="module")
def desktop_streamlit_server():
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless=true", f"--server.address={HOST}",
            f"--server.port={PORT}", "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
        ],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Streamlit exited early with code {process.returncode}"
                )
            try:
                with urllib.request.urlopen(BASE_URL, timeout=2) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise TimeoutError("Streamlit desktop smoke server did not become ready")
        yield BASE_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_desktop_browser_has_no_horizontal_overflow_or_unapproved_execution_control(
    desktop_streamlit_server,
):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.goto(desktop_streamlit_server, wait_until="domcontentloaded", timeout=30000)
        page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=30000)
        page.get_by_label("Describe a task").wait_for(timeout=30000)

        metrics = page.evaluate("""() => ({
          viewport: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          title: document.querySelector('h1')?.textContent || ''
        })""")
        assert metrics["documentWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["bodyWidth"] <= metrics["viewport"] + 2, metrics
        assert metrics["title"], metrics

        labels = page.get_by_role("button").all_text_contents()
        assert not any(
            any(token in label.casefold() for token in (
                "execute", "run task", "approve action", "auto-run"
            ))
            for label in labels
        ), labels

        context.close()
        browser.close()
