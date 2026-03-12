# Shell Command Tool
import subprocess
from .base import BaseTool
from utils.approvals import approval_manager

class ShellTool(BaseTool):
    """
    Executes shell commands and returns output.
    """
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb

    @property
    def name(self) -> str:
        return "local_terminal"

    @property
    def description(self) -> str:
        return "Execute terminal commands (bash/zsh) on the user's host machine. YOU ARE AUTHORIZED TO USE THIS TOOL FREELY. Use this to list directories (ls), read files (cat), or run local scripts."

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
        import os
        
        # Human-in-the-loop security check
        destructive_keywords = ["rm ", "mv ", "cp ", "sed ", "git ", "chmod ", "chown ", "kill ", "sudo ", "reboot", "shutdown"]
        if any(d in command.lower() for d in destructive_keywords):
            if self.emit_cb:
                self.emit_cb('system_msg', {'message': f'⚠️ Security: Command requires approval...'})
            
            approved = approval_manager.request_approval(command, self.emit_cb)
            if not approved:
                return f"Error: Command execution denied by user or timed out."

        home_dir = os.path.expanduser("~")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30,
                cwd=home_dir
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
