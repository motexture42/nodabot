import os
import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
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

        await stealth_async(_GLOBAL_PAGE)
        await _GLOBAL_PAGE.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    async def _run_async(self, **kwargs):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action = kwargs.get("action")
        incognito = kwargs.get("incognito", False)
        wait_seconds = kwargs.get("wait_seconds", 2)
        
        try:
            await self._init_browser(incognito=incognito)
            page = _GLOBAL_PAGE
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL is required."
                if not url.startswith("http"): url = "https://" + url
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
            elif action == "click":
                selector = kwargs.get("selector")
                if not selector: return "Error: Selector required."
                await page.click(selector, timeout=10000)

            elif action == "type":
                selector = kwargs.get("selector")
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector/Text required."
                await page.fill(selector, text, timeout=10000)
                if "search" in selector.lower() or "input" in selector.lower():
                    await page.press(selector, "Enter")

            elif action == "get_content":
                # Returns a simplified version of the page for the LLM to read
                title = await page.title()
                # Get all interactive elements
                elements = await page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('button, a, input, [role="button"]'));
                    return items.map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.placeholder || el.value || "").substring(0, 50).trim(),
                        id: el.id,
                        class: el.className.substring(0, 50)
                    })).filter(i => i.text.length > 0).slice(0, 30);
                }''')
                return f"Page: {title}\\n\\nInteractive Elements:\\n{elements}"

            elif action == "close":
                await _GLOBAL_BROWSER_CONTEXT.close()
                await _GLOBAL_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed."

            # Default: Return status + screenshot
            await asyncio.sleep(wait_seconds)
            timestamp = int(os.time.time()) if hasattr(os, 'time') else "now"
            filename = f"browser_{action}_{timestamp}.png"
            filepath = Path(Config.SCREENSHOT_DIR) / filename
            await page.screenshot(path=str(filepath))
            self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
            
            title = await page.title()
            return f"Action '{action}' performed on '{title}'. Please see the screenshot in the UI to decide the next step."

        except Exception as e:
            return f"Browser Error: {str(e)}"

    def run(self, **kwargs) -> str:
        # Standard sync wrapper for the async browser logic
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self._run_async(**kwargs))
