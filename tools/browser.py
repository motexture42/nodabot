import os
import time
import logging
import traceback
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import Stealth
from .base import BaseTool
from config import Config

# Configure logging
logger = logging.getLogger("BrowserTool")

# Global instances to persist across tool re-initialization
_GLOBAL_SYNC_PLAYWRIGHT = None
_GLOBAL_BROWSER_CONTEXT = None
_GLOBAL_PAGE = None

class BrowserControllerTool(BaseTool):
    """
    Advanced Browser Controller using Synchronous Playwright for maximum stability in threaded apps.
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
        return "Control a real web browser. Supports persistent sessions and high-speed discovery. Use 'get_content' to see the page."

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
        """Forcefully kills any Chromium processes that might be locking the profile."""
        if not _GLOBAL_BROWSER_CONTEXT:
            try:
                cmd = f"ps aux | grep '{self.user_data_dir}' | grep -v grep | awk '{{print $2}}' | xargs kill -9"
                subprocess.run(cmd, shell=True, capture_output=True)
                time.sleep(0.5)
            except: pass

    def _init_browser(self):
        global _GLOBAL_SYNC_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        
        # Health Check
        if _GLOBAL_BROWSER_CONTEXT and _GLOBAL_PAGE:
            try:
                _GLOBAL_PAGE.title()
                return 
            except:
                logger.warning("Browser session lost. Re-initializing...")
                _GLOBAL_BROWSER_CONTEXT = None

        self._cleanup_zombie_processes()

        try:
            _GLOBAL_SYNC_PLAYWRIGHT = sync_playwright().start()
            
            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-infobars"]
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            
            _GLOBAL_BROWSER_CONTEXT = _GLOBAL_SYNC_PLAYWRIGHT.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                args=launch_args,
                viewport={'width': 1280, 'height': 800},
                user_agent=ua
            )
            _GLOBAL_PAGE = _GLOBAL_BROWSER_CONTEXT.pages[0]
            
            # Apply stealth
            Stealth().apply_stealth_sync(_GLOBAL_PAGE)
            logger.info("Sync Browser session established.")
        except Exception as e:
            logger.error(f"Browser Init Error: {e}")
            raise

    def run(self, **kwargs) -> str:
        global _GLOBAL_SYNC_PLAYWRIGHT, _GLOBAL_BROWSER_CONTEXT, _GLOBAL_PAGE
        action, selector = kwargs.get("action"), kwargs.get("selector")
        wait_seconds = kwargs.get("wait_seconds", 1)
        
        try:
            if action == "close":
                if _GLOBAL_BROWSER_CONTEXT: 
                    _GLOBAL_BROWSER_CONTEXT.close()
                    _GLOBAL_SYNC_PLAYWRIGHT.stop()
                _GLOBAL_BROWSER_CONTEXT = _GLOBAL_SYNC_PLAYWRIGHT = _GLOBAL_PAGE = None
                return "Browser closed."
            
            self._init_browser()
            page = _GLOBAL_PAGE
            
            if selector and ":contains(" in selector:
                selector = selector.replace(":contains(", ":has-text(")
            
            if action == "navigate":
                url = kwargs.get("url")
                if not url: return "Error: URL required."
                if not url.startswith("http"): url = "https://" + url
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                result_msg = f"Navigated to {url}"
                
            elif action == "refresh":
                page.reload(wait_until="domcontentloaded")
                result_msg = "Page refreshed."

            elif action == "click":
                if not selector: return "Error: Selector required."
                # Scan main page and frames
                target = page
                if not page.query_selector(selector):
                    for frame in page.frames:
                        if frame.query_selector(selector):
                            target = frame; break
                
                target.wait_for_selector(selector, state="visible", timeout=10000)
                target.click(selector, timeout=10000, force=True)
                result_msg = f"Clicked {selector}"

            elif action == "type":
                text = kwargs.get("text")
                if not selector or not text: return "Error: Selector/Text required."
                page.wait_for_selector(selector, state="visible", timeout=10000)
                page.fill(selector, text, timeout=10000)
                if any(k in selector.lower() for k in ["search", "input", "user"]): page.press(selector, "Enter")
                result_msg = f"Typed into {selector}"

            elif action == "scroll":
                page.evaluate("window.scrollBy(0, 800)")
                result_msg = "Scrolled down."

            elif action == "get_content":
                title = page.title()
                # Fast flat elements map
                elements = page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('button, a, input, [role="button"]'))
                        .filter(el => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        })
                        .map(el => ({
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.placeholder || "").substring(0, 50).trim(),
                            id: el.id
                        })).slice(0, 40);
                }''')
                return f"Page: {title}\\nURL: {page.url}\\n\\nInteractive Elements:\\n{elements}"

            elif action == "screenshot":
                ts = int(time.time())
                filepath = Path(Config.SCREENSHOT_DIR) / f"manual_{ts}.png"
                page.screenshot(path=str(filepath), timeout=15000)
                self._emit("artifact", {"type": "image", "content": f"/screenshots/manual_{ts}.png"})
                return "Screenshot captured."

            # Auto-feedback
            if action in ["navigate", "click", "type", "scroll", "refresh"]:
                time.sleep(wait_seconds)
                ts = int(time.time())
                filepath = Path(Config.SCREENSHOT_DIR) / f"browser_{action}_{ts}.png"
                page.screenshot(path=str(filepath), timeout=15000)
                self._emit("artifact", {"type": "image", "content": f"/screenshots/browser_{action}_{ts}.png"})
                return f"{result_msg}. Snapshot sent to UI."

            return result_msg
        except Exception as e:
            logger.error(f"Browser Error: {e}\n{traceback.format_exc()}")
            return f"Browser Error: {str(e)}"
