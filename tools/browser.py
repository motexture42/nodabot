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
    Advanced Browser Controller with stealth, persistence, and self-healing.
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
            "Control a real web browser. Supports persistent sessions. "
            "This tool is FRAME-AWARE. For text-based selectors, use 'text=...' or 'span:has-text(\"...\")'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "scroll", "get_content", "screenshot", "close", "refresh"],
                    "description": "The action to perform."
                },
                "url": {"type": "string", "description": "URL for navigate."},
                "selector": {"type": "string", "description": "Selector for click/type."},
                "text": {"type": "string", "description": "Text to type."},
                "incognito": {"type": "boolean", "default": False},
                "wait_seconds": {"type": "integer", "default": 2}
            },
            "required": ["action"]
        }

    async def _init_browser(self, incognito=False):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE, _GLOBAL_LOOP
        
        # SELF-HEALING: Check if existing session is actually alive
        if _GLOBAL_BROWSER_CONTEXT and _GLOBAL_PAGE:
            try:
                await asyncio.wait_for(_GLOBAL_PAGE.title(), timeout=2.0)
                return # Still alive
            except:
                logger.warning("Existing browser session seems dead. Restarting...")
                try:
                    await _GLOBAL_BROWSER_CONTEXT.close()
                    await _GLOBAL_PLAYWRIGHT.stop()
                except: pass
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None

        try:
            _GLOBAL_LOOP = asyncio.get_running_loop()
            _GLOBAL_PLAYWRIGHT = await async_playwright().start()
            launch_args = [
                "--disable-blink-features=AutomationControlled", 
                "--no-sandbox", 
                "--disable-infobars",
                "--disable-dev-shm-usage"
            ]
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            
            if incognito:
                browser = await _GLOBAL_PLAYWRIGHT.chromium.launch(headless=False, args=launch_args)
                _GLOBAL_BROWSER_CONTEXT = await browser.new_context(viewport={'width': 1280, 'height': 800}, user_agent=ua)
                _GLOBAL_PAGE = await _GLOBAL_BROWSER_CONTEXT.new_page()
            else:
                _GLOBAL_BROWSER_CONTEXT = await _GLOBAL_PLAYWRIGHT.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir), 
                    headless=False, 
                    args=launch_args,
                    viewport={'width': 1280, 'height': 800}, 
                    user_agent=ua,
                    ignore_default_args=["--disable-component-update"]
                )
                _GLOBAL_PAGE = _GLOBAL_BROWSER_CONTEXT.pages[0]
                
            await Stealth().apply_stealth_async(_GLOBAL_PAGE)
            # Short wait for initialization
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            _GLOBAL_BROWSER_CONTEXT = None
            raise

    async def _find_target(self, page: Page, selector: str):
        try:
            if await page.query_selector(selector): return page
        except: pass
        for frame in page.frames:
            try:
                if await frame.query_selector(selector): return frame
            except: continue
        return None

    async def _take_safe_screenshot(self, page, filename):
        """Captures a screenshot with relaxed but safe limits."""
        filepath = Path(Config.SCREENSHOT_DIR) / filename
        try:
            # animations="disabled" can sometimes hang if the page is mid-transition
            # We'll use a simpler call but with a solid timeout
            await asyncio.wait_for(page.screenshot(
                path=str(filepath), 
                timeout=15000,
                type="png"
            ), timeout=18.0)
            self._emit("artifact", {"type": "image", "content": f"/screenshots/{filename}"})
            return True
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return False

    async def _run_async(self, **kwargs):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action, selector = kwargs.get("action"), kwargs.get("selector")
        incognito, wait_seconds = kwargs.get("incognito", False), kwargs.get("wait_seconds", 2)
        
        try:
            if action == "close":
                if _GLOBAL_BROWSER_CONTEXT: await _GLOBAL_BROWSER_CONTEXT.close()
                if _GLOBAL_PLAYWRIGHT: await _GLOBAL_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed successfully."
            
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
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    result_msg = f"Navigated to {url}"
                except Exception as e:
                    result_msg = f"Navigation reached timeout ({str(e)}), check UI for state."
                
            elif action == "refresh":
                await page.reload(wait_until="domcontentloaded")
                result_msg = "Page refreshed."

            elif action == "click":
                if not selector: return "Error: Selector required."
                target = await self._find_target(page, selector)
                if not target: return f"Error: Element '{selector}' not found."
                await target.wait_for_selector(selector, state="visible", timeout=8000)
                await target.click(selector, timeout=8000, force=True)
                result_msg = f"Clicked {selector}"

            elif action == "type":
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector/Text required."
                target = await self._find_target(page, selector)
                if not target: return f"Error: Element '{selector}' not found."
                await target.fill(selector, text, timeout=8000)
                if any(k in selector.lower() for k in ["search", "input", "user", "pass"]):
                    await target.press(selector, "Enter")
                result_msg = f"Typed into {selector}"

            elif action == "scroll":
                await page.evaluate("window.scrollBy(0, 800)")
                result_msg = "Scrolled down."

            elif action == "get_content":
                try:
                    title = await asyncio.wait_for(page.title(), timeout=5.0)
                except: title = "Untitled Page"
                
                all_elements = []
                async def scrape_frame(f, prefix=""):
                    try:
                        items = await asyncio.wait_for(f.evaluate('''() => {
                            return Array.from(document.querySelectorAll('button, a, input, [role="button"], [aria-label]')).map(el => ({
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || el.placeholder || el.getAttribute('aria-label') || "").substring(0, 60).trim(),
                                id: el.id
                            })).filter(i => (i.text.length > 0 || i.id)).slice(0, 20);
                        }'''), timeout=4.0)
                        for i in items: i['frame'] = prefix or "main"; all_elements.append(i)
                    except: pass
                
                await scrape_frame(page)
                # Only 1 more frame to be ultra-safe on heavy sites
                if len(page.frames) > 1: await scrape_frame(page.frames[1], "f_1")
                
                return f"Page: {title} (URL: {page.url})\\n\\nInteractive Elements:\\n{all_elements[:40]}"

            elif action == "screenshot":
                ts = int(time.time())
                success = await self._take_safe_screenshot(page, f"manual_{ts}.png")
                return "Screenshot captured." if success else "Error: Screenshot failed."

            # Auto-feedback logic
            if action in ["navigate", "click", "type", "scroll", "refresh"]:
                await asyncio.sleep(wait_seconds)
                ts = int(time.time())
                await self._take_safe_screenshot(page, f"browser_{action}_{ts}.png")
                return f"{result_msg}. Snapshot sent to UI."

            return result_msg
        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {e}")
            return f"Browser Error: {str(e)}"

    def run(self, **kwargs) -> str:
        global _GLOBAL_LOOP
        if _GLOBAL_LOOP and _GLOBAL_LOOP.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._run_async(**kwargs), _GLOBAL_LOOP)
                return future.result(timeout=40)
            except Exception as e:
                logger.warning(f"Loop error: {e}")
                _GLOBAL_LOOP = None # Reset loop reference
        
        try:
            return asyncio.run(self._run_async(**kwargs))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._run_async(**kwargs))
