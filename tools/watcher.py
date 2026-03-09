from tools.base import BaseTool
import os
import json

class SystemWatcherTool(BaseTool):
    """Allows the agent to monitor specific directories for file system events."""
    
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        # Registry of active watchers: { path: { task: str, id: str } }
        self.active_watchers = {}

    @property
    def name(self) -> str:
        return "manage_watchers"

    @property
    def description(self) -> str:
        return "Sets up a background monitor for a specific directory. When a file is created or modified, the agent will automatically execute the specified task."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "list"],
                    "description": "The action to perform."
                },
                "path": {
                    "type": "string",
                    "description": "The full path to the directory to watch."
                },
                "task": {
                    "type": "string",
                    "description": "The instruction for the agent when an event occurs (e.g., 'Summarize this PDF')."
                },
                "watcher_id": {
                    "type": "string",
                    "description": "A unique ID for the watcher (required for 'stop')."
                }
            },
            "required": ["action"]
        }

    def run(self, action: str, path: str = None, task: str = None, watcher_id: str = None, **kwargs) -> str:
        if action == "start":
            if not path or not task:
                return "Error: 'path' and 'task' are required to start a watcher."
            
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                return f"Error: Path {abs_path} does not exist."
            
            wid = watcher_id or f"watch_{abs_path.replace('/', '_')[-20:]}"
            self.active_watchers[wid] = {
                "path": abs_path,
                "task": task,
                "status": "active"
            }
            
            if self.emit_cb:
                self.emit_cb("watchers_update", {"watchers": self.active_watchers})
                
            return f"Watcher {wid} started on {abs_path}. Task: {task}"
            
        elif action == "stop":
            if not watcher_id or watcher_id not in self.active_watchers:
                return f"Error: Watcher ID '{watcher_id}' not found."
            del self.active_watchers[watcher_id]
            
            if self.emit_cb:
                self.emit_cb("watchers_update", {"watchers": self.active_watchers})
                
            return f"Watcher {watcher_id} stopped."
            
        elif action == "list":
            if not self.active_watchers:
                return "No active watchers."
            return json.dumps(self.active_watchers, indent=2)
            
        return "Unknown action."
