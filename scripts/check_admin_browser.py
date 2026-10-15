"""Browser regression for HTTP form Origin and session-cookie behavior.

Run after installing Playwright and Chromium. Uses an isolated temporary database.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

PASSWORD = "Isolated browser test password!"


def main():
    with tempfile.TemporaryDirectory() as directory:
        env = os.environ | {
            "PICKAFLICK_DATA_DIR": directory,
            "PICKAFLICK_CONFIG": str(Path("config.example.yaml").resolve()),
            "PICKAFLICK_ADMIN_ALLOW_HTTP": "true",
            "NO_PROXY": "127.0.0.1,localhost,homelab",
        }
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       env=env, check=True)
        subprocess.run(
            [sys.executable, "-c",
             "from app.admin.security import set_password; set_password(" + repr(PASSWORD) + ")"],
            env=env, check=True,
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://homelab:{port}"
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port)],
            env=env,
        )
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                        break
                except (urllib.error.URLError, TimeoutError):
                    if server.poll() is not None:
                        raise RuntimeError("Test server exited before startup")
                    time.sleep(0.1)
            else:
                raise RuntimeError("Test server did not become healthy")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(args=[
                    "--host-resolver-rules=MAP homelab 127.0.0.1", "--no-proxy-server",
                ])
                try:
                    # Reproduce the old response policy in an actual form document.
                    with browser.new_context() as old:
                        page = old.new_page()
                        page.goto(base + "/admin/login")
                        page.evaluate("""() => {
                            const meta = document.createElement('meta');
                            meta.name = 'referrer';
                            meta.content = 'no-referrer';
                            document.head.appendChild(meta);
                        }""")
                        page.get_by_label("Admin-wachtwoord").fill(PASSWORD)
                        with page.expect_response(
                            lambda r: r.request.method == "POST" and
                            r.url == base + "/admin/login"
                        ) as rejected:
                            page.get_by_role("button", name="Inloggen", exact=True).click()
                        assert rejected.value.request.all_headers().get("origin") == "null"
                        assert rejected.value.status == 403
                    # A normal HTTP hostname (not localhost) models the LAN deployment.
                    with browser.new_context() as context:
                        page = context.new_page()
                        page.goto(base + "/admin/login")
                        page.get_by_label("Admin-wachtwoord").fill(PASSWORD)
                        with page.expect_response(
                            lambda r: r.request.method == "POST" and
                            r.url == base + "/admin/login"
                        ) as accepted:
                            page.get_by_role("button", name="Inloggen", exact=True).click()
                        assert accepted.value.request.all_headers().get("origin") == base
                        assert accepted.value.status == 303
                        page.wait_for_url(base + "/admin/settings")
                        expect(page.get_by_role("heading", name="Beheerinstellingen")).to_be_visible()
                        cookies = context.cookies()
                        cookie = next(c for c in cookies if c["name"] == "pickaflick_admin")
                        assert cookie["httpOnly"] and cookie["sameSite"] == "Strict"
                        assert not cookie["secure"]
                        page.get_by_role("button", name="Instellingen opslaan").click()
                        page.wait_for_url(base + "/admin/settings?saved=1")
                        expect(page.get_by_role("status")).to_have_text("Instellingen opgeslagen.")
                        page.get_by_role("button", name="Uitloggen", exact=True).click()
                        page.wait_for_url(base + "/admin/login")
                finally:
                    browser.close()
            print("Chromium: old policy reproduced; HTTP login, settings and logout passed.")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
