import os
import asyncio
import base64
import time
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from .base import BaseTool
from config import Config

# Global instances to persist across tool re-initialization
_GLOBAL_PLAYWRIGHT = None
_GLOBAL_BROWSER_CONTEXT = None
_GLOBAL_PAGE = None

class BrowserControllerTool(BaseTool):
    """
    Advanced Browser Controller with stealth capabilities and persistent sessions.
    Allows the agent to interact with websites like a human.
    """
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        self.user_data_dir = Path.home() / ".nodabot" / "browser_session"
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str:
        return "browser_controller"

    @property
    def description(self) -> str:
        return (
            "Control a real web browser to navigate, click, type, and scrape data. "
            "Supports persistent sessions and incognito mode. "
            "IMPORTANT: For text-based selectors, use 'text=...' or 'span:has-text(\"...\")'. "
            "Avoid using ':contains()'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "scroll", "get_content", "screenshot", "close"],
                    "description": "The action to perform in the browser."
                },
                "url": {"type": "string", "description": "The URL to navigate to (required for 'navigate')."},
                "selector": {"type": "string", "description": "CSS selector for the element (required for 'click' and 'type')."},
                "text": {"type": "string", "description": "Text to type (required for 'type')."},
                "incognito": {
                    "type": "boolean", 
                    "description": "If true, starts a fresh session without saved cookies/history. Defaults to false (persistent).",
                    "default": False
                },
                "wait_seconds": {"type": "integer", "description": "Seconds to wait after action. Defaults to 2.", "default": 2}
            },
            "required": ["action"]
        }

    async def _init_browser(self, incognito=False):
        """Initializes the global browser context if not already running."""
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        
        if _GLOBAL_BROWSER_CONTEXT:
            return

        _GLOBAL_PLAYWRIGHT = await async_playwright().start()
        
        # Human-like launch arguments
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--window-size=1280,800"
        ]

        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        if incognito:
            browser = await _GLOBAL_PLAYWRIGHT.chromium.launch(headless=False, args=launch_args)
            _GLOBAL_BROWSER_CONTEXT = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent=user_agent
            )
            _GLOBAL_PAGE = await _GLOBAL_BROWSER_CONTEXT.new_page()
        else:
            _GLOBAL_BROWSER_CONTEXT = await _GLOBAL_PLAYWRIGHT.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                args=launch_args,
                viewport={'width': 1280, 'height': 800},
                user_agent=user_agent
            )
            _GLOBAL_PAGE = _GLOBAL_BROWSER_CONTEXT.pages[0]

        await Stealth().apply_stealth_async(_GLOBAL_PAGE)
        await _GLOBAL_PAGE.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    async def _run_async(self, **kwargs):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action = kwargs.get("action")
        incognito = kwargs.get("incognito", False)
        wait_seconds = kwargs.get("wait_seconds", 2)
        
        try:
            await self._init_browser(incognito=incognito)
            page = _GLOBAL_PAGE
            
            result_msg = ""
            
            # Smart Selector Translation: fix common LLM hallucination (:contains -> :has-text)
            selector = kwargs.get("selector")
            if selector and ":contains(" in selector:
                selector = selector.replace(":contains(", ":has-text(")
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL is required."
                if not url.startswith("http"): url = "https://" + url
                await page.goto(url, wait_until="networkidle", timeout=60000)
                result_msg = f"Navigated to {url}"
                
            elif action == "click":
                if not selector: return "Error: Selector required."
                await page.wait_for_selector(selector, state="visible", timeout=10000)
                await page.click(selector, timeout=10000, force=True)
                result_msg = f"Clicked {selector}"

            elif action == "type":
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector/Text required."
                await page.wait_for_selector(selector, state="visible", timeout=10000)
                await page.fill(selector, text, timeout=10000)
                if "search" in selector.lower() or "input" in selector.lower():
                    await page.press(selector, "Enter")
                result_msg = f"Typed text into {selector}"

            elif action == "scroll":
                await page.evaluate("window.scrollBy(0, 500)")
                result_msg = "Scrolled down 500px."

            elif action == "get_content":
                title = await page.title()
                elements = await page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('button, a, input, [role="button"], [aria-label]'));
                    return items.map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.placeholder || el.value || el.getAttribute('aria-label') || "").substring(0, 100).trim(),
                        id: el.id,
                        class: el.className.substring(0, 50),
                        role: el.getAttribute('role')
                    })).filter(i => (i.text.length > 0 || i.id)).slice(0, 50);
                }''')
                return f"Page: {title}\\n\\nInteractive Elements Map:\\n{elements}"

            elif action == "screenshot":
                timestamp = int(time.time())
                filename = f"manual_{timestamp}.png"
                filepath = Path(Config.SCREENSHOT_DIR) / filename
                await page.screenshot(path=str(filepath))
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                return f"Manual screenshot saved as {filename}"

            elif action == "close":
                if _GLOBAL_BROWSER_CONTEXT:
                    await _GLOBAL_BROWSER_CONTEXT.close()
                if _GLOBAL_PLAYWRIGHT:
                    await _GLOBAL_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed."

            # Auto-feedback logic for interactive actions
            if action in ["navigate", "click", "type", "scroll"]:
                await asyncio.sleep(wait_seconds)
                timestamp = int(time.time())
                filename = f"browser_{action}_{timestamp}.png"
                filepath = Path(Config.SCREENSHOT_DIR) / filename
                await page.screenshot(path=str(filepath))
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                title = await page.title()
                return f"{result_msg} on '{title}'. Snapshot sent to UI. Use 'get_content' to see updated element map if needed."

            return result_msg

        except Exception as e:
            return f"Browser Error: {str(e)}"

    def run(self, **kwargs) -> str:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self._run_async(**kwargs))
