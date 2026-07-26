"""
End-to-end tests using Playwright.

Requires the server running on http://localhost:8000.
Run with: uv run pytest tests/test_e2e.py
"""

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "base_url": "http://localhost:8000",
    }


class TestCompileQuery:
    def test_page_loads(self, page):
        page.goto("/")
        assert page.title() == "Predicate"
        assert page.locator("textarea").is_visible()

    def test_compile_query(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.fill("Show active customers in Germany")
        textarea.press("Control+Enter")
        page.wait_for_selector("text=SQL", timeout=30000)
        sql_tab = page.locator("button:has-text('SQL')")
        assert sql_tab.is_visible()

    def test_compile_shows_results(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.fill("Count all customers")
        textarea.press("Control+Enter")
        page.wait_for_selector("text=Results", timeout=30000)
        results_tab = page.locator("button:has-text('Results')")
        assert results_tab.is_visible()


class TestKeyboardShortcuts:
    def test_click_opens_palette(self, page):
        page.goto("/")
        palette_btn = page.locator("button[aria-label^='Open command palette']")
        assert palette_btn.is_visible()
        palette_btn.click()
        page.wait_for_timeout(200)
        palette = page.locator("[role='dialog'][aria-label='Command palette']")
        assert palette.is_visible()

    def test_escape_closes_palette(self, page):
        page.goto("/")
        page.locator("button[aria-label^='Open command palette']").click()
        page.wait_for_timeout(300)
        palette = page.locator("[role='dialog'][aria-label='Command palette']")
        assert palette.is_visible()
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        assert page.locator("[role='dialog']").count() == 0

    def test_t_cycles_theme(self, page):
        page.goto("/")
        initial = page.locator("html").get_attribute("data-theme")
        page.keyboard.press("t")
        page.wait_for_timeout(200)
        after = page.locator("html").get_attribute("data-theme")
        assert initial != after


class TestHistory:
    def test_query_appears_in_history(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.fill("Count all customers")
        textarea.press("Control+Enter")
        page.wait_for_selector("text=Completed", timeout=60000)
        page.keyboard.press("h")
        page.wait_for_selector("[aria-label=\"Query history\"]", timeout=10000)
        history_panel = page.locator("[aria-label=\"Query history\"]")
        assert history_panel.locator("text=No queries yet").count() == 0


class TestAccessibility:
    def test_textarea_focusable(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.focus()
        focused = page.evaluate("() => document.activeElement.tagName")
        assert focused == "TEXTAREA"

    def test_tab_navigates_to_button(self, page):
        page.goto("/")
        page.keyboard.press("Tab")
        focused = page.evaluate("() => document.activeElement.tagName")
        assert focused in ("BUTTON", "TEXTAREA", "A", "INPUT")


class TestAuthentication:
    def test_status_bar_shows_compiling(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.fill("Show all customers")
        textarea.press("Control+Enter")
        page.wait_for_selector("text=Executing", timeout=5000)
        assert page.locator("text=Executing").is_visible()


class TestFailureHandling:
    def test_empty_prompt_ignored(self, page):
        page.goto("/")
        textarea = page.locator("textarea")
        textarea.fill("   ")
        textarea.press("Control+Enter")
        page.wait_for_timeout(1000)
        status = page.locator("text=Compiling").count() + page.locator("text=Executing").count()
        assert status == 0
