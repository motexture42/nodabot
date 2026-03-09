# DuckDuckGo Free Search Tool
import urllib.request
import urllib.parse
import re
from .base import BaseTool

class DuckDuckGoSearchTool(BaseTool):
    """
    Performs a free web search using DuckDuckGo Lite.
    No API key required.
    """
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for real-time information, news, or facts. Returns a text summary of search results."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g., 'latest news in Italy')."
                }
            },
            "required": ["query"]
        }

    def run(self, **kwargs) -> str:
        query = kwargs.get("query")
        # DuckDuckGo Lite URL
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8")
                
                # Simple regex to strip HTML tags and get readable text
                # DuckDuckGo Lite puts results in a table
                # This is a 'micro' way to parse without BeautifulSoup
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Return the first 3000 characters to keep context small
                return f"Search Results for '{query}':\n\n{text[:3000]}..."
        except Exception as e:
            return f"Error performing search: {str(e)}"
