# Base Tool Definition
from abc import ABC, abstractmethod
import json

class BaseTool(ABC):
    """
    All tools must inherit from this class. 
    It ensures the LLM gets a clear JSON schema for tool discovery.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """Return a JSON schema for the tool's arguments."""
        pass

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Actual execution logic for the tool."""
        pass

    def pre_run(self, **kwargs) -> None:
        """Hook called BEFORE the tool's main logic. Can be used for snapshots/logs."""
        pass

    def post_run(self, result: str, **kwargs) -> None:
        """Hook called AFTER the tool's main logic. Can be used for cleanup/tracking."""
        pass

    def to_openai_schema(self) -> dict:
        """Converts tool definition to OpenAI-compatible function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
