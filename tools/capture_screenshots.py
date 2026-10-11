#!/usr/bin/env python3
"""Capture the real PastySpace UI with disposable, fictional sample data.

Prerequisites (use a virtual environment and a separate app checkout):
    git clone --branch main https://github.com/mubix/pastyspace.git ../pastyspace-app
    python -m pip install -r ../pastyspace-app/requirements.txt playwright pillow
    python -m playwright install chromium
    python tools/capture_screenshots.py --app-dir ../pastyspace-app

If Chromium is installed by the OS, pass --chromium /usr/bin/chromium.
The server binds only to localhost on a free port. Its database and sample
attachment live in a temporary directory and are removed on exit. No application
files or existing paste databases are changed. Screenshots are saved as lossless
WebP images; the UI is neither restyled nor otherwise altered for the capture.
"""

import argparse
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = 1791714600  # 2026-10-11 10:30 UTC; fictional sample timestamp.

PYTHON_SAMPLE = '''from dataclasses import dataclass


@dataclass(frozen=True)
class Mission:
    destination: str
    crew: tuple[str, ...]
    snacks: int

    def ready_for_launch(self) -> bool:
        return self.snacks >= len(self.crew) * 3


mission = Mission(
    destination="The Moon",
    crew=("Ada", "Linus", "Pasty"),
    snacks=42,
)

if mission.ready_for_launch():
    print(f"Next stop: {mission.destination}")
    print("Notes saved. Snacks packed. Let's go.")
'''

MARKDOWN_SAMPLE = '''## One small paste. One giant snack supply.

The launch brief is ready to share. **Flight plan is final.**

| Cargo | Status |
| :--- | :--- |
| Navigation script | Checked and packed |
| Emergency biscuits | 42 aboard |
| Return ticket | In the glove box |

> Mission rule: leave the Moon tidier than you found it.

Next checkpoint: **Sea of Tranquility**, just after lunch.
'''

ROUTE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="130" viewBox="0 0 920 130">
<rect width="920" height="130" rx="12" fill="#213448"/>
<g fill="#91b1cc"><circle cx="156" cy="28" r="2"/><circle cx="682" cy="28" r="2"/>
<circle cx="539" cy="106" r="2"/><circle cx="338" cy="19" r="2"/><circle cx="789" cy="106" r="2"/></g>
<path d="M110 66 Q440 -2 810 65" fill="none" stroke="#92bdc9" stroke-width="2" stroke-dasharray="7 8"/>
<circle cx="99" cy="64" r="29" fill="#7fccc3"/><path d="M78 45l19 2 8 11-11 10 10 13-16 6-13-19Z" fill="#367e87"/>
<circle cx="820" cy="64" r="29" fill="#f6ddac"/><g fill="#d5b87b"><circle cx="810" cy="56" r="7"/><circle cx="831" cy="74" r="9"/><circle cx="837" cy="50" r="4"/></g>
<g transform="translate(456 41) rotate(7)"><path d="M-17 0l-12 12 16-3M-17 0l-12-12 16 3" fill="#ee8770"/>
<path d="M-21-7Q0-16 20 0Q0 16-21 7Z" fill="#fff5dc"/><circle cx="3" cy="0" r="5" fill="#376c8a"/>
<path d="M-23-4l-13 4 13 4" fill="#ffc661"/></g>
<g fill="#dce8ee" font-family="Arial, sans-serif" font-size="12" text-anchor="middle">
<text x="99" y="113">Home base</text><text x="456" y="88">A very short commute</text><text x="820" y="113">The Moon</text></g>
</svg>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, required=True,
                        help="Path to a separate checkout of the application's main branch")
    parser.add_argument("--chromium", help="Optional system Chromium executable")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "assets" / "screenshots")
    args = parser.parse_args()
    app_file = args.app_dir.resolve() / "app.py"
    if not app_file.is_file():
        parser.error(f"Application not found at {app_file}; use a checkout of the main branch")

    from PIL import Image
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pastyspace-capture-") as temporary:
        database = Path(temporary) / "samples.sqlite3"
        previous_database = os.environ.get("PASTY_DB")
        os.environ["PASTY_DB"] = str(database)
        spec = importlib.util.spec_from_file_location("pastyspace_capture_app", app_file)
        module = importlib.util.module_from_spec(spec)
        previous_module = sys.modules.get(spec.name)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            if previous_module is None:
                sys.modules.pop(spec.name, None)
            else:
                sys.modules[spec.name] = previous_module
            if previous_database is None:
                os.environ.pop("PASTY_DB", None)
            else:
                os.environ["PASTY_DB"] = previous_database

        server = make_server("127.0.0.1", 0, module.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        address = f"http://127.0.0.1:{server.server_port}"
        attachment = Path(temporary) / "flight-plan.svg"
        attachment.write_text(ROUTE_SVG, encoding="utf-8")

        def fix_sample_time(slug):
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE pastes SET created_at=? WHERE slug=?",
                                   (FIXED_TIME, slug))

        try:
            with sync_playwright() as playwright:
                launch = {"headless": True}
                if args.chromium:
                    launch["executable_path"] = args.chromium
                browser = playwright.chromium.launch(**launch)
                page = browser.new_page(viewport={"width": 1200, "height": 900},
                                        device_scale_factor=1, locale="en-US",
                                        timezone_id="UTC", reduced_motion="reduce")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def capture(name, height):
                    page.set_viewport_size({"width": 1200, "height": height})
                    page.mouse.move(1190, height - 10)
                    page.evaluate("document.activeElement.blur()")
                    page.evaluate("document.fonts.ready")
                    page.wait_for_function("Array.from(document.images).every(image => image.complete)")
                    page.evaluate("window.scrollTo(0, 0)")
                    data = page.screenshot(type="png", full_page=False,
                                           animations="disabled", caret="hide")
                    output = args.output / f"{name}.webp"
                    Image.open(io.BytesIO(data)).save(output, "WEBP", lossless=True)
                    print(f"Saved {output} (1200 x {height})")

                # All sample pastes are created through the actual browser form.
                page.goto(address + "/mission-control.py")
                page.locator("#title").fill("Mission control, in 22 lines")
                page.locator("#syntax").select_option("python")
                page.locator("#body").fill(PYTHON_SAMPLE)
                page.locator("#save").click()
                page.wait_for_selector(".locked")
                fix_sample_time("mission-control.py")
                page.reload()
                page.wait_for_selector(".hljs .hljs-keyword")
                capture("code", 760)

                page.goto(address + "/lunar-launch-checklist")
                page.locator("#title").fill("Lunar launch checklist")
                page.locator("#syntax").select_option("markdown")
                page.locator("#body").fill(MARKDOWN_SAMPLE)
                page.locator("#picker").set_input_files(attachment)
                page.wait_for_selector(".att img")
                capture("editor", 940)
                page.locator("#save").click()
                page.wait_for_selector(".locked")
                fix_sample_time("lunar-launch-checklist")
                page.reload()
                page.wait_for_selector(".markdown table")
                page.locator(".file-img img").scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('.file-img img').naturalWidth > 0")
                capture("markdown", 900)

                # Verify the demonstrated source toggle, raw body and immutability.
                page.locator("#toggleSrc").click()
                assert page.locator("#rendered pre").count() == 1
                page.locator("#toggleSrc").click()
                assert page.locator(".markdown table").count() == 1
                raw = page.request.get(address + "/raw/mission-control.py")
                # Multipart browser forms serialize line endings as CRLF.
                assert raw.status == 200 and raw.text().replace("\r\n", "\n") == PYTHON_SAMPLE
                conflict = page.request.post(address + "/mission-control.py", data="overwrite")
                assert conflict.status == 409
                assert not errors, "Browser errors: " + "; ".join(errors)
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    main()
