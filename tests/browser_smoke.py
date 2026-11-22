"""Optional browser smoke test. Install requirements-dev.txt first.
Uses a temporary local server and stops it on completion.
CAD_CHROME_PATH=/path/to/chrome python tests/browser_smoke.py
Or: python -m playwright install chromium, then run without CAD_CHROME_PATH.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
import uvicorn


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as output:
        os.environ['CAD_OUTPUT_DIR'] = output
        config = uvicorn.Config('app.main:app', host='127.0.0.1', port=8765, log_level='warning')
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.1)
            if not server.started:
                raise RuntimeError('Test server did not start')
            with sync_playwright() as p:
                options = {'headless':True, 'args':['--no-sandbox', '--enable-unsafe-swiftshader']}
                if os.getenv('CAD_CHROME_PATH'):
                    options['executable_path'] = os.environ['CAD_CHROME_PATH']
                browser = p.chromium.launch(**options)
                page = browser.new_page(viewport={'width':1360, 'height':1100}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                # All app assets are local. Block external traffic to verify offline viewer.
                page.route('**/*', lambda route: route.continue_() if route.request.url.startswith('http://127.0.0.1:8765/') else route.abort())
                page.goto('http://127.0.0.1:8765/')
                page.wait_for_selector('#generate:not([disabled])')
                page.wait_for_selector('#viewer canvas')
                for name in ('plate', 'bushing', 'bracket', 'enclosure'):
                    page.select_option('#part-type', name)
                    page.click('#generate')
                    page.wait_for_function("document.querySelector('#status').textContent.includes('checks passed')")
                    page.wait_for_function("document.querySelector('#empty-state').hidden === true")
                    page.wait_for_selector('#generate:not([disabled])')
                    assert page.locator('#result').is_visible()
                    assert page.locator('#step-link').get_attribute('href').endswith('/part.step')
                    print('Browser generated and previewed:', name)
                    if name == 'bracket':
                        page.screenshot(path=str(root/'examples'/'desktop-preview.png'), full_page=True)
                # A dimension edit must invalidate old downloads and preview.
                page.fill('#dim-length', '90')
                assert not page.locator('#result').is_visible()
                page.click('#generate')
                page.wait_for_function("document.querySelector('#empty-state').hidden === true")
                page.wait_for_selector('#generate:not([disabled])')
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(root/'examples'/'mobile-preview.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                assert not errors, errors
                browser.close()
                print('PASS: 4 offline previews, stale-output clearing, dimension edit, mobile layout, no JS errors.')
        finally:
            server.should_exit = True
            thread.join(timeout=15)

if __name__ == '__main__':
    main()
