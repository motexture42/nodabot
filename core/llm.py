# Core LLM Interaction Logic
import json
import requests
from config import Config

class LLMProvider:
    """
    Minimalist interface to interact with local LLMs 
    (LM Studio, vLLM, Ollama) via OpenAI-compatible endpoints.
    """
    def __init__(self, base_url: str = Config.BASE_URL, api_key: str = Config.API_KEY, model: str = Config.DEFAULT_MODEL):
        self.base_url = f"{base_url.rstrip('/')}/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.model = model

    def chat_completion(self, messages: list, tools: list = None, tool_choice: str = "auto", model_override: str = None):
        """Perform a single chat completion turn."""
        payload = {
            "model": model_override or self.model,
            "messages": messages,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = [tool.to_openai_schema() for tool in tools]
            if tool_choice != "auto":
                payload["tool_choice"] = tool_choice

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=Config.TIMEOUT)
            if response.status_code != 200:
                print(f"LLM API Error {response.status_code}: {response.text}")
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        except Exception as e:
            error_msg = f"LLM Error: {str(e)}"
            if 'response' in locals() and response is not None:
                error_msg += f" - Status: {response.status_code} - Body: {response.text}"
            return {"role": "assistant", "content": error_msg}
