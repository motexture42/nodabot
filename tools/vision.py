# Vision and Screenshot Tool
import os
import subprocess
import base64
from datetime import datetime
from pathlib import Path
from PIL import Image
from .base import BaseTool
from config import Config

class ScreenshotTool(BaseTool):
    """
    Captures a screenshot and uses a vision LLM to describe it.
    """
    def __init__(self, llm_provider=None, emit_cb=None):
        self.llm = llm_provider
        self.emit_cb = emit_cb
        self.screenshot_dir = Path(Config.SCREENSHOT_DIR)
        self.screenshot_dir.mkdir(exist_ok=True)

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str:
        return "capture_screen"

    @property
    def description(self) -> str:
        return "Take a screenshot of the user's screen and analyze it. Use this if the user asks 'what is on my screen' or to debug visual UI issues."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why are you taking this screenshot? (e.g., 'Looking for an error message')"
                }
            },
            "required": ["reason"]
        }

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def run(self, **kwargs) -> str:
        reason = kwargs.get("reason", "No reason provided")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = self.screenshot_dir / filename

        self._emit("system_msg", {"message": f"📸 Capturing screen: {reason}..."})

        try:
            # 1. Capture screen using macOS built-in tool
            subprocess.run(["screencapture", "-x", str(filepath)], check=True)
            
            # 2. Resize image to save tokens/bandwidth (max 1024px)
            with Image.open(filepath) as img:
                img.thumbnail((1024, 1024))
                img.save(filepath)

            # 3. Analyze with Vision LLM (if provided)
            if not self.llm:
                return f"Screenshot saved to {filepath}, but no vision LLM is configured to analyze it."

            base64_image = self._encode_image(filepath)
            
            self._emit("system_msg", {"message": "🧠 Analyzing visual data..."})

            # Format for vision-capable OpenAI compatible endpoints
            payload = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Describe what is happening on this screen. Context: {reason}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }

            # Use the Vision Model specified in config
            result = self.llm.chat_completion([payload], model_override=Config.VISION_MODEL) 
            description = result.get("content", "Failed to get visual description.")

            return f"Visual Observation of the Screen:\n\n{description}\n\n(Saved as: {filename})"

        except Exception as e:
            return f"Error capturing/analyzing screen: {str(e)}"
