import os
import asyncio
import base64
import time
import logging
from pathlib import Path
from playwright.async_api import async_playwright, Page, Frame
from playwright_stealth import Stealth
from .base import BaseTool
from config import Config

# Configure logging
logger = logging.getLogger("BrowserTool")

# Global instances to persist across tool re-initialization
_GLOBAL_PLAYWRIGHT = None
_GLOBAL_BROWSER_CONTEXT = None
_GLOBAL_PAGE = None
_GLOBAL_LOOP = None

class BrowserControllerTool(BaseTool):
    """
    Advanced Browser Controller with stealth, persistence, and multi-frame support.
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
            "Control a real web browser. Supports persistent sessions and incognito. "
            "IMPORTANT: This tool is FRAME-AWARE. It will automatically find elements in iframes. "
            "For text-based selectors, use 'text=...' or 'span:has-text(\"...\")'. Avoid using ':contains()'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "scroll", "get_content", "screenshot", "close"],
                    "description": "The action to perform."
                },
                "url": {"type": "string", "description": "URL for navigate."},
                "selector": {"type": "string", "description": "Selector for click/type. Scans all frames automatically."},
                "text": {"type": "string", "description": "Text to type."},
                "incognito": {"type": "boolean", "default": False},
                "wait_seconds": {"type": "integer", "default": 2}
            },
            "required": ["action"]
        }

    async def _init_browser(self, incognito=False):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE, _GLOBAL_LOOP
        if _GLOBAL_BROWSER_CONTEXT: return
        
        _GLOBAL_LOOP = asyncio.get_running_loop()
        logger.info("Initializing new browser instance...")
        _GLOBAL_PLAYWRIGHT = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled", 
            "--no-sandbox", 
            "--disable-infobars"
        ]
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        
        if incognito:
            browser = await _GLOBAL_PLAYWRIGHT.chromium.launch(headless=False, args=launch_args)
            _GLOBAL_BROWSER_CONTEXT = await browser.new_context(viewport={'width': 1280, 'height': 800}, user_agent=ua)
            _GLOBAL_PAGE = await _GLOBAL_BROWSER_CONTEXT.new_page()
        else:
            _GLOBAL_BROWSER_CONTEXT = await _GLOBAL_PLAYWRIGHT.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir), headless=False, args=launch_args,
                viewport={'width': 1280, 'height': 800}, user_agent=ua
            )
            _GLOBAL_PAGE = _GLOBAL_BROWSER_CONTEXT.pages[0]
            
        await Stealth().apply_stealth_async(_GLOBAL_PAGE)
        logger.info("Browser initialized successfully.")

    async def _find_target(self, page: Page, selector: str):
        """Finds the selector in the main page or any of its frames."""
        try:
            if await page.query_selector(selector):
                return page
        except: pass
        
        for frame in page.frames:
            try:
                if await frame.query_selector(selector):
                    return frame
            except: continue
        return None

    async def _run_async(self, **kwargs):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action = kwargs.get("action")
        selector = kwargs.get("selector")
        incognito = kwargs.get("incognito", False)
        wait_seconds = kwargs.get("wait_seconds", 2)
        
        try:
            # Handle CLOSE action immediately
            if action == "close":
                if _GLOBAL_BROWSER_CONTEXT:
                    logger.info("Closing browser context...")
                    await _GLOBAL_BROWSER_CONTEXT.close()
                if _GLOBAL_PLAYWRIGHT:
                    logger.info("Stopping playwright...")
                    await _GLOBAL_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed successfully."
            
            # For all other actions, initialize if needed
            await self._init_browser(incognito=incognito)
            page = _GLOBAL_PAGE
            result_msg = ""
            
            if selector and ":contains(" in selector:
                selector = selector.replace(":contains(", ":has-text(")
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL required."
                if not url.startswith("http"): url = "https://" + url
                try:
                    await page.goto(url, wait_until="load", timeout=30000)
                except Exception as e:
                    title = await page.title()
                    if title: result_msg = f"Navigated to {url} (background still loading)."
                    else: return f"Navigation Error: {str(e)}"
                if not result_msg: result_msg = f"Navigated to {url}"
                
            elif action == "click":
                if not selector: return "Error: Selector required."
                target = await self._find_target(page, selector)
                if not target: return f"Error: Element '{selector}' not found."
                await target.wait_for_selector(selector, state="visible", timeout=5000)
                await target.click(selector, timeout=5000, force=True)
                result_msg = f"Clicked {selector}"

            elif action == "type":
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector/Text required."
                target = await self._find_target(page, selector)
                if not target: return f"Error: Element '{selector}' not found."
                await target.wait_for_selector(selector, state="visible", timeout=5000)
                await target.fill(selector, text, timeout=5000)
                if any(k in selector.lower() for k in ["search", "input", "user", "pass"]):
                    await target.press(selector, "Enter")
                result_msg = f"Typed into {selector}"

            elif action == "scroll":
                await page.evaluate("window.scrollBy(0, 500)")
                result_msg = "Scrolled 500px."

            elif action == "get_content":
                title = await page.title()
                all_elements = []
                async def scrape_frame(f, prefix=""):
                    try:
                        items = await f.evaluate('''() => {
                            return Array.from(document.querySelectorAll('button, a, input, [role="button"], [aria-label]')).map(el => ({
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || el.placeholder || el.value || el.getAttribute('aria-label') || "").substring(0, 50).trim(),
                                id: el.id
                            })).filter(i => (i.text.length > 0 || i.id)).slice(0, 20);
                        }''')
                        for i in items:
                            i['frame'] = prefix or "main"
                            all_elements.append(i)
                    except: pass
                await scrape_frame(page)
                for i, frame in enumerate(page.frames[1:]):
                    await scrape_frame(frame, f"frame_{i}")
                return f"Page: {title}\\n\\nInteractive Elements (All Frames):\\n{all_elements[:50]}"

            elif action == "screenshot":
                ts = int(time.time())
                filename = f"manual_{ts}.png"
                filepath = Path(Config.SCREENSHOT_DIR) / filename
                # Try capture with timeout
                try:
                    await page.screenshot(path=str(filepath), timeout=10000)
                except Exception as e:
                    logger.warning(f"Screenshot failed, retrying... {e}")
                    await asyncio.sleep(1)
                    await page.screenshot(path=str(filepath), timeout=10000)
                
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                return f"Screenshot saved: {filename}"

            # Auto-feedback for interactive actions
            if action in ["navigate", "click", "type", "scroll"]:
                await asyncio.sleep(wait_seconds)
                ts = int(time.time())
                filename = f"browser_{action}_{ts}.png"
                await page.screenshot(path=str(Path(Config.SCREENSHOT_DIR) / filename))
                self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
                return f"{result_msg}. Snapshot sent to UI."

            return result_msg
        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {e}")
            return f"Browser Error: {str(e)}"

    def run(self, **kwargs) -> str:
        global _GLOBAL_LOOP
        
        # If we have a stored loop, we MUST try to use it for thread safety with Playwright
        if _GLOBAL_LOOP and _GLOBAL_LOOP.is_running():
            try:
                # If we are in the SAME thread/loop, run normally
                try:
                    current_loop = asyncio.get_event_loop()
                    if current_loop == _GLOBAL_LOOP:
                        return current_loop.run_until_complete(self._run_async(**kwargs))
                except RuntimeError:
                    pass

                # If we are in a DIFFERENT thread, post to the original loop
                future = asyncio.run_coroutine_threadsafe(self._run_async(**kwargs), _GLOBAL_LOOP)
                return future.result(timeout=40)
            except Exception as e:
                logger.warning(f"Failed to use original browser loop: {e}")
                # Fallback to creating a new context if the old loop is dead
                if kwargs.get("action") == "close":
                    _GLOBAL_LOOP = None
                    return "Browser already closed or unreachable."
        
        # Standard execution if no loop exists or original loop failed
        try:
            return asyncio.run(self._run_async(**kwargs))
        except RuntimeError:
            # Handle nested event loops (e.g. if called inside another async context)
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(self._run_async(**kwargs))
