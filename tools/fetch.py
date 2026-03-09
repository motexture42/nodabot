# Web Content Fetcher Tool - Raw Text Mode
import urllib.request
import re
import json
from .base import BaseTool

class WebFetchTool(BaseTool):
    """
    Fetches a URL and returns the cleaned text content directly.
    """
    def __init__(self, llm_provider=None, emit_cb=None):
        self.llm = llm_provider
        self.emit_cb = emit_cb

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Fetches the raw text content of a URL. Useful for getting up-to-date information quickly."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch."
                }
            },
            "required": ["url"]
        }

    def run(self, **kwargs) -> str:
        url = kwargs.get("url")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            self._emit("system_msg", {"message": f"🌐 Fetching content from {url}..."})
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="ignore")
                
                # Clean HTML: remove script, style, and nav elements
                clean_html = re.sub(r'<(script|style|header|footer|nav|aside)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
                # Strip all other tags
                text = re.sub(r'<[^>]+>', ' ', clean_html)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                
                if not text:
                    return f"Error: No readable text found at {url}"

                # Return raw cleaned text (truncated to avoid context blowup)
                return f"Content Source: {url}\n\n{text[:8000]}"
                
        except Exception as e:
            return f"Error fetching URL {url}: {str(e)}"
