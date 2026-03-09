import os
import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from .base import BaseTool
from config import Config

class BrowserControllerTool(BaseTool):
    """
    Advanced Browser Controller with stealth capabilities and persistent sessions.
    Allows the agent to interact with websites like a human.
    """
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        self.user_data_dir = Path.home() / ".nodabot" / "browser_session"
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser_context = None
        self._page = None

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
            "Supports persistent sessions (cookies/login) and incognito mode. "
            "Use this for complex web tasks, logging into sites, or advanced research."
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
        """Initializes the browser context if not already running."""
        if self._browser_context:
            return

        self._playwright = await async_playwright().start()
        
        # Human-like launch arguments
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--window-size=1280,800",
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]

        if incognito:
            # Incognito: Standard browser launch + clean context
            browser = await self._playwright.chromium.launch(headless=False, args=launch_args)
            self._browser_context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        else:
            # Persistent: Uses a local directory for cookies/storage
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                args=launch_args,
                viewport={'width': 1280, 'height': 800}
            )

        # Apply stealth to the context
        self._page = await self._browser_context.new_page() if incognito else self._browser_context.pages[0]
        await stealth_async(self._page)
        
        # Remove webdriver detection
        await self._page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    async def _run_async(self, **kwargs):
        action = kwargs.get("action")
        incognito = kwargs.get("incognito", False)
        wait_seconds = kwargs.get("wait_seconds", 2)
        
        try:
            await self._init_browser(incognito=incognito)
            
            result_msg = ""
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL is required for navigate."
                if not url.startswith("http"): url = "https://" + url
                await self._page.goto(url, wait_until="networkidle", timeout=60000)
                result_msg = f"Navigated to {url}"

            elif action == "click":
                selector = kwargs.get("selector")
                if not selector: return "Error: Selector is required for click."
                await self._page.click(selector, timeout=10000)
                result_msg = f"Clicked element: {selector}"

            elif action == "type":
                selector = kwargs.get("selector")
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector and Text are required for type."
                await self._page.fill(selector, text, timeout=10000)
                # Simulate pressing 'Enter' if it looks like a search/login
                if "search" in selector.lower() or "input" in selector.lower():
                    await self._page.press(selector, "Enter")
                result_msg = f"Typed text into {selector}"

            elif action == "scroll":
                await self._page.evaluate("window.scrollBy(0, 500)")
                result_msg = "Scrolled down 500px."

            elif action == "get_content":
                content = await self._page.content()
                # Simplified text extraction
                text = await self._page.evaluate("document.body.innerText")
                return f"Browser Content:\n\n{text[:10000]}"

            elif action == "screenshot":
                timestamp = int(os.time.time()) if hasattr(os, 'time') else "current"
                filename = f"browser_{timestamp}.png"
                filepath = Path(Config.SCREENSHOT_DIR) / filename
                await self._page.screenshot(path=str(filepath))
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                return f"Screenshot saved as {filename}"

            elif action == "close":
                await self._browser_context.close()
                await self._playwright.stop()
                self._browser_context = None
                self._playwright = None
                return "Browser closed."

            # Auto-screenshot after actions for visual feedback to user
            if action in ["navigate", "click", "type"]:
                await asyncio.sleep(wait_seconds)
                filename = f"action_result_{action}.png"
                filepath = Path(Config.SCREENSHOT_DIR) / filename
                await self._page.screenshot(path=str(filepath))
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                title = await self._page.title()
                return f"Action '{action}' complete. Current Page: '{title}'. Snapshot sent to UI."

            return result_msg

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
