# File Manipulation Tool
import os
from pathlib import Path
from .base import BaseTool

class FileTool(BaseTool):
    """
    Handles file operations: read, write, and append.
    """
    @property
    def name(self) -> str:
        return "file_manager"

    @property
    def description(self) -> str:
        return "Read, write, or append to files. Use this to save research, create code, or manage project files."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "append"],
                    "description": "The action to perform."
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file."
                },
                "content": {
                    "type": "string",
                    "description": "Content to write or append (required for write/append)."
                }
            },
            "required": ["action", "file_path"]
        }

    def run(self, **kwargs) -> str:
        action = kwargs.get("action")
        file_path = kwargs.get("file_path")
        content = kwargs.get("content", "")
        
        # Ensure path is absolute or resolved from home
        p = Path(file_path).expanduser()
        if not p.is_absolute():
            path = (Path.home() / p).resolve()
        else:
            path = p.resolve()
        
        try:
            if action == "read":
                if not path.exists():
                    return f"Error: File {file_path} does not exist."
                with open(path, 'r', encoding='utf-8') as f:
                    data = f.read()
                    return f"Content of {file_path}:\n\n{data[:5000]}..." if len(data) > 5000 else data

            elif action == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"Successfully wrote to {file_path}."

            elif action == "append":
                if not path.exists():
                    return self.run(action="write", file_path=file_path, content=content)
                with open(path, 'a', encoding='utf-8') as f:
                    f.write("\n" + content)
                return f"Successfully appended to {file_path}."

        except Exception as e:
            return f"Error during file operation: {str(e)}"

    def pre_run(self, **kwargs) -> None:
        action = kwargs.get("action")
        snapshot_mgr = kwargs.get("snapshot_mgr")
        if action in ["write", "append"] and snapshot_mgr:
            snapshot_mgr.create_snapshot(label=f"file_{action}")
