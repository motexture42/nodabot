import urllib.request
import urllib.parse
import json
import re
from .base import BaseTool
from config import Config

class WebSearchTool(BaseTool):
    """
    Performs a web search. Uses Tavily API if configured,
    otherwise falls back to DuckDuckGo Lite.
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

    def _tavily_search(self, query: str, api_key: str) -> str:
        url = "https://api.tavily.com/search"
        data = json.dumps({
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False,
            "max_results": 5
        }).encode('utf-8')
        
        headers = {
            "Content-Type": "application/json"
        }
        
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                output = f"Tavily Search Results for '{query}':\n\n"
                if "answer" in result and result["answer"]:
                    output += f"Summary Answer:\n{result['answer']}\n\n"
                    
                for idx, res in enumerate(result.get("results", [])):
                    output += f"{idx+1}. {res.get('title', 'No Title')}\n"
                    output += f"   URL: {res.get('url', '')}\n"
                    output += f"   Content: {res.get('content', '')}\n\n"
                    
                return output[:4000] # Cap length
        except Exception as e:
            return f"Tavily API Error: {str(e)}"

    def _ddg_search(self, query: str) -> str:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8")
                
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text).strip()
                
                return f"DuckDuckGo Search Results for '{query}':\n\n{text[:3000]}..."
        except Exception as e:
            return f"Error performing search: {str(e)}"

    def run(self, **kwargs) -> str:
        query = kwargs.get("query")
        
        if Config.TAVILY_API_KEY:
            return self._tavily_search(query, Config.TAVILY_API_KEY)
        else:
            return self._ddg_search(query)
