# Core LLM Interaction Logic using OpenAI SDK
import os
import json
from openai import OpenAI
from config import Config

class LLMProvider:
    """
    Interface to interact with LLMs using the official OpenAI Python SDK.
    Supports local endpoints (LM Studio, vLLM, Ollama) if base_url is set,
    otherwise defaults to the official OpenAI API.
    """
    def __init__(self, base_url: str = Config.BASE_URL, api_key: str = Config.API_KEY, model: str = Config.DEFAULT_MODEL):
        self.model = model
        
        # Determine client parameters based on user instruction: 
        # "do not set base url and do not pass it on openai client if BASE_URL param is set to an empty string"
        client_kwargs = {"api_key": api_key}
        if base_url and base_url.strip():
            client_kwargs["base_url"] = base_url.rstrip('/')
            
        self.client = OpenAI(**client_kwargs, max_retries=2)

    def chat_completion(self, messages: list, tools: list = None, tool_choice: str = "auto", model_override: str = None):
        """Perform a single chat completion turn using the OpenAI SDK."""
        try:
            params = {
                "model": model_override or self.model,
                "messages": messages,
                "stream": False,
                "stop": ["<|im_end|>", "<|im_start|>", "user\n", "User:"]
            }
            
            if tools:
                params["tools"] = [tool.to_openai_schema() for tool in tools]
                if tool_choice != "auto":
                    params["tool_choice"] = tool_choice

            response = self.client.chat.completions.create(**params)
            message = response.choices[0].message
            
            # Manually construct a dict that is compatible with the Agent's expected format
            result = {
                "role": "assistant",
                "content": message.content or ""
            }
            
            if message.tool_calls:
                result["tool_calls"] = []
                for tool_call in message.tool_calls:
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
            
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"LLM Error: {str(e)}"
            return {"role": "assistant", "content": error_msg}
