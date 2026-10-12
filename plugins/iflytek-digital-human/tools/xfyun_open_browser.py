#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open platform URLs in a detached browser process and keep it alive."""
import json
import sys
import time

import xfyun_common as xc
from playwright.sync_api import sync_playwright


def main():
    urls = json.loads(sys.argv[1])
    cookies = xc.load_cookies()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        if cookies:
            context.add_cookies([
                {"name": name, "value": value, "domain": ".xfyun.cn", "path": "/"}
                for name, value in cookies.items()
            ])

        for _, url in urls:
            context.new_page().goto(url)

        while browser.is_connected():
            time.sleep(0.5)


if __name__ == "__main__":
    main()
