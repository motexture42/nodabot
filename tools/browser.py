import os
import asyncio
import base64
import time
import logging
import traceback
import subprocess
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
    Advanced Browser Controller with zombie process cleanup and resilient session management.
    """
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        self.user_data_dir = Path.home() / ".nodabot" / "browser_session"
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str: return "browser_controller"

    @property
    def description(self) -> str:
        return "Control a real web browser. Supports persistent sessions and high-speed discovery."

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
                "url": {"type": "string"},
                "selector": {"type": "string"},
                "text": {"type": "string"},
                "wait_seconds": {"type": "integer", "default": 1}
            },
            "required": ["action"]
        }

    def _cleanup_zombie_processes(self):
        """Surgically kills only orphaned Chromium processes related to this tool."""
        try:
            # We only do this if we are NOT currently tracking a context
            if not _GLOBAL_BROWSER_CONTEXT:
                logger.info("Cleaning up orphaned browser processes...")
                cmd = f"ps aux | grep '{self.user_data_dir}' | grep -v grep | awk '{{print $2}}' | xargs kill -9"
                subprocess.run(cmd, shell=True, capture_output=True)
                time.sleep(0.5)
        except: pass

    async def _init_browser(self, incognito=False):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE, _GLOBAL_LOOP
        
        # 1. Resilient Health Check
        if _GLOBAL_BROWSER_CONTEXT and _GLOBAL_PAGE:
            try:
                # Increased timeout to 10s for heavy sites like LinkedIn
                await asyncio.wait_for(_GLOBAL_PAGE.title(), timeout=10.0)
                return 
            except Exception as e:
                logger.warning(f"Browser health check failed ({e}). Restarting session...")
                try:
                    await _GLOBAL_BROWSER_CONTEXT.close()
                    await _GLOBAL_PLAYWRIGHT.stop()
                except: pass
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None

        # 2. Safety Cleanup
        self._cleanup_zombie_processes()

        # 3. Launch
        try:
            _GLOBAL_LOOP = asyncio.get_running_loop()
            _GLOBAL_PLAYWRIGHT = await async_playwright().start()
            
            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-infobars"]
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
                    user_agent=ua
                )
                _GLOBAL_PAGE = _GLOBAL_BROWSER_CONTEXT.pages[0]
                
            await Stealth().apply_stealth_async(_GLOBAL_PAGE)
            logger.info("Browser session established.")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}\n{traceback.format_exc()}")
            raise

    async def _run_async(self, **kwargs):
        global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action, selector = kwargs.get("action"), kwargs.get("selector")
        wait_seconds = kwargs.get("wait_seconds", 1)
        
        try:
            if action == "close":
                if _GLOBAL_BROWSER_CONTEXT: 
                    await _GLOBAL_BROWSER_CONTEXT.close()
                    await _GLOBAL_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed."
            
            await self._init_browser()
            page = _GLOBAL_PAGE
            result_msg = ""
            
            if selector and ":contains(" in selector:
                selector = selector.replace(":contains(", ":has-text(")
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL required."
                if not url.startswith("http"): url = "https://" + url
                try: 
                    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    result_msg = f"Navigated to {url}"
                except:
                    result_msg = f"Navigated to {url} (partial load)"
                
            elif action == "refresh":
                await page.reload(wait_until="domcontentloaded")
                result_msg = "Page refreshed."

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
                if any(k in selector.lower() for k in ["search", "input", "user"]): await page.press(selector, "Enter")
                result_msg = f"Typed into {selector}"

            elif action == "scroll":
                await page.evaluate("window.scrollBy(0, 800)")
                result_msg = "Scrolled down."

            elif action == "get_content":
                try:
                    title = await asyncio.wait_for(page.title(), timeout=5.0)
                    snapshot = await asyncio.wait_for(page.accessibility.snapshot(), timeout=8.0)
                    def simplify(node):
                        res = []
                        if node.get("role") in ["link", "button", "textbox", "checkbox"] or node.get("name"):
                            res.append({"role": node.get("role"), "name": node.get("name"), "value": node.get("value")})
                        if "children" in node:
                            for child in node["children"]: res.extend(simplify(child))
                        return res
                    elements = simplify(snapshot) if snapshot else []
                    return f"Page: {title} (URL: {page.url})\\n\\nInteractive Elements:\\n{elements[:50]}"
                except Exception as e:
                    return f"Content Error: {str(e)}"

            elif action == "screenshot":
                ts = int(time.time())
                filepath = Path(Config.SCREENSHOT_DIR) / f"manual_{ts}.png"
                try:
                    await asyncio.wait_for(page.screenshot(path=str(filepath), timeout=15000), timeout=18.0)
                    self._emit("artifact", {"type": "image", "content": f"/screenshots/manual_{ts}.png"})
                    return "Screenshot captured."
                except Exception as e:
                    return f"Error: Screenshot failed: {str(e)}"

            # Auto-feedback
            if action in ["navigate", "click", "type", "scroll", "refresh"]:
                await asyncio.sleep(wait_seconds)
                ts = int(time.time())
                filepath = Path(Config.SCREENSHOT_DIR) / f"browser_{action}_{ts}.png"
                try:
                    await asyncio.wait_for(page.screenshot(path=str(filepath), timeout=10000), timeout=12.0)
                    self._emit("artifact", {"type": "image", "content": f"/screenshots/browser_{action}_{ts}.png"})
                except: pass
                return f"{result_msg}. Snapshot sent to UI."

            return result_msg
        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {e}\n{traceback.format_exc()}")
            return f"Browser Error: {str(e)}"

    def run(self, **kwargs) -> str:
        global _GLOBAL_LOOP
        if _GLOBAL_LOOP and _GLOBAL_LOOP.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._run_async(**kwargs), _GLOBAL_LOOP)
                return future.result(timeout=40)
            except Exception as e:
                if kwargs.get("action") == "close": _GLOBAL_LOOP = None
                return f"Browser Error: {str(e)}"
        try:
            return asyncio.run(self._run_async(**kwargs))
        except RuntimeError:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(self._run_async(**kwargs))
