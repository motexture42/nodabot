# Shell Command Tool
import subprocess
from .base import BaseTool

class ShellTool(BaseTool):
    """
    Executes shell commands and returns output.
    """
    @property
    def name(self) -> str:
        return "execute_shell"

    @property
    def description(self) -> str:
        return "Run a bash/zsh command on the host. Use with caution."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The literal shell command to run."
                }
            },
            "required": ["command"]
        }

    def run(self, **kwargs) -> str:
        command = kwargs.get("command")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        except Exception as e:
            return f"Error executing shell: {str(e)}"

    def pre_run(self, **kwargs) -> None:
        command = kwargs.get("command", "").lower()
        snapshot_mgr = kwargs.get("snapshot_mgr")
        # Snapshot before potentially destructive commands
        destructive = ["rm ", "mv ", "cp ", "sed ", "git ", "chmod ", "chown "]
        if any(d in command for d in destructive) and snapshot_mgr:
            snapshot_mgr.create_snapshot(label="shell_cmd")
