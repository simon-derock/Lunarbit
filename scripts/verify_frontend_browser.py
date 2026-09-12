"""Run browser-level smoke checks against a running Lunarbit frontend.

The verifier is intentionally opt-in: CI can run it in an environment with
Playwright and a live API, while ordinary Python contract jobs do not need a
browser binary.  It checks the user-visible graph shell, responsive layout,
menu containment, and (optionally) the streamed Ask path.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrowserConfig:
    url: str
    chat_question: str | None
    headed: bool
    strict: bool


def _parse_args() -> BrowserConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5173/",
        help="running Vite URL (default: %(default)s)",
    )
    parser.add_argument(
        "--chat-question",
        help="submit a real Ask question after the shell checks",
    )
    parser.add_argument("--headed", action="store_true", help="show Chromium while checking")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return failure when the Python Playwright package is unavailable",
    )
    args = parser.parse_args()
    return BrowserConfig(
        url=args.url,
        chat_question=args.chat_question,
        headed=args.headed,
        strict=args.strict,
    )


def _require_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is not installed; install it with `uv pip install playwright` "
            "and run `playwright install chromium`."
        ) from error
    return sync_playwright


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _check_shell(page: Any, config: BrowserConfig) -> None:
    page.goto(config.url, wait_until="domcontentloaded")
    page.locator("main.app-shell").wait_for(state="visible", timeout=15_000)

    # A failed API must be rendered as an explicit state, never as synthetic
    # graph content.  A live projection instead exposes the canvas.
    graph_ready = page.locator("canvas").count() > 0
    unavailable = page.get_by_text("live graph unavailable", exact=False).count() > 0
    _assert(graph_ready or unavailable, "graph shell did not reach a verifiable state")

    controls = page.locator("header .header-controls")
    _assert(controls.is_visible(), "graph controls are not visible")
    _assert(controls.locator("button").count() >= 3, "view/style/theme controls are incomplete")


def _check_mobile_layout(page: Any, config: BrowserConfig) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="domcontentloaded")
    page.locator("main.app-shell").wait_for(state="visible", timeout=15_000)

    dimensions = page.evaluate(
        """() => ({
          width: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          height: document.documentElement.clientHeight,
        })"""
    )
    _assert(
        dimensions["scrollWidth"] <= dimensions["width"] + 1,
        f"mobile page overflows horizontally: {dimensions}",
    )
    ask = page.get_by_label("Ask Lunarbit")
    _assert(ask.is_visible(), "Ask control is not visible at iPhone viewport")

    controls = page.locator("header .header-controls")
    buttons = controls.locator("button")
    _assert(buttons.count() >= 3, "mobile graph controls are incomplete")
    buttons.nth(0).click()
    menu = page.locator(".menu-popover:visible").last
    menu.wait_for(state="visible", timeout=2_000)
    option_count = menu.locator(":scope > button").count()
    _assert(option_count >= 2, "view menu exposes fewer than two profiles")
    menu_box = menu.bounding_box()
    _assert(menu_box is not None, "view menu has no layout box")
    _assert(menu_box["x"] >= 0, "view menu leaves the left mobile viewport")
    _assert(
        menu_box["x"] + menu_box["width"] <= 390,
        f"view menu leaves the right mobile viewport: {menu_box}",
    )
    page.keyboard.press("Escape")


def _check_streamed_chat(page: Any, question: str) -> None:
    ask = page.get_by_label("Ask Lunarbit")
    ask.fill(question)
    ask.press("Enter")
    answer = page.locator(".ask-answer")
    answer.wait_for(state="visible", timeout=45_000)
    _assert(
        answer.get_by_text("verified response", exact=False).count() == 1,
        "answer metadata missing",
    )
    _assert(answer.locator(".ask-meta").count() == 1, "answer provenance metadata missing")


def run(config: BrowserConfig) -> int:
    try:
        sync_playwright = _require_playwright()
    except RuntimeError as error:
        if config.strict:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        print(f"SKIP: {error}")
        return 0

    errors: list[str] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=not config.headed)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                _check_shell(page, config)
                _check_mobile_layout(page, config)
                if config.chat_question:
                    _check_streamed_chat(page, config.chat_question)
            finally:
                browser.close()
        except Exception as error:
            errors.append(str(error))

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: desktop graph shell, mobile layout, and menu containment")
    if config.chat_question:
        print("PASS: streamed Ask answer contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(_parse_args()))
