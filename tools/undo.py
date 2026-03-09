from .base import BaseTool
import json

class UndoTool(BaseTool):
    """
    Allows the agent to list and restore snapshots.
    Useful for rolling back mistakes or failed experiments.
    """
    @property
    def name(self) -> str:
        return "undo_changes"

    @property
    def description(self) -> str:
        return "List available snapshots or restore the workspace to a previous state. Use this to 'undo' a mistake."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "restore"],
                    "description": "Whether to list available snapshots or restore to one."
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "The ID of the snapshot to restore to (omit for the latest one)."
                }
            },
            "required": ["action"]
        }

    def run(self, action: str, snapshot_id: str = None, **kwargs) -> str:
        # Note: snapshot_mgr is passed via pre_run/post_run or directly by the Agent
        # But for 'run', we need it. Let's assume the Agent passes it or we get it from kwargs.
        snapshot_mgr = kwargs.get("snapshot_mgr")
        if not snapshot_mgr:
            return "Error: Snapshot manager not available for this tool."

        if action == "list":
            snapshots = snapshot_mgr.list_snapshots()
            if not snapshots:
                return "No snapshots available."
            return "Available Snapshots (ID is the filename):\n" + "\n".join(snapshots)
            
        elif action == "restore":
            return snapshot_mgr.restore_snapshot(snapshot_id)
            
        return "Unknown action."

    def pre_run(self, **kwargs) -> None:
        # We don't want to create a snapshot BEFORE an undo, 
        # as it might push out older, more useful snapshots.
        pass
