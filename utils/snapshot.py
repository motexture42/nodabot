import os
import shutil
import time
import logging
from pathlib import Path

logger = logging.getLogger("SnapshotManager")

class SnapshotManager:
    """
    Handles filesystem snapshots for 'Undo' capabilities.
    Stores snapshots in a hidden .snapshots directory.
    """
    def __init__(self, base_dir: str = ".", storage_dir: str = ".snapshots"):
        self.base_dir = Path(base_dir).resolve()
        self.storage_dir = self.base_dir / storage_dir
        self.storage_dir.mkdir(exist_ok=True)
        self.max_snapshots = 5

    def _get_timestamp(self):
        return int(time.time())

    def create_snapshot(self, label: str = "auto") -> str:
        """Creates a full copy of the current workspace (excluding ignored dirs)."""
        ts = self._get_timestamp()
        snapshot_path = self.storage_dir / f"{ts}_{label}"
        
        # Define what to ignore (don't snapshot the snapshots, venv, or git)
        ignore_dirs = [".snapshots", "venv", ".git", "__pycache__", "sessions", "screenshots"]
        
        try:
            def ignore_func(directory, contents):
                return [c for c in contents if c in ignore_dirs or (Path(directory) / c).is_dir() and c in ignore_dirs]

            shutil.copytree(self.base_dir, snapshot_path, ignore=ignore_func, dirs_exist_ok=True)
            
            # Prune old snapshots
            self._prune()
            logger.info(f"Snapshot created: {snapshot_path.name}")
            return snapshot_path.name
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return f"Error: {str(e)}"

    def restore_snapshot(self, snapshot_id: str = None) -> str:
        """Restores the workspace to a specific snapshot state."""
        try:
            snapshots = sorted(self.storage_dir.glob("*"), reverse=True)
            if not snapshots:
                return "Error: No snapshots available."

            target = None
            if snapshot_id:
                target = self.storage_dir / snapshot_id
            else:
                target = snapshots[0] # Default to latest

            if not target or not target.exists():
                return f"Error: Snapshot {snapshot_id} not found."

            # Risky operation: Clear current workspace and copy back
            # We don't delete ignored dirs
            ignore_dirs = [".snapshots", "venv", ".git", "__pycache__", "sessions", "screenshots", ".env"]
            
            for item in self.base_dir.iterdir():
                if item.name not in ignore_dirs:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            shutil.copytree(target, self.base_dir, dirs_exist_ok=True)
            logger.info(f"Workspace restored to: {target.name}")
            return f"Successfully restored to snapshot: {target.name}"
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return f"Error during restore: {str(e)}"

    def list_snapshots(self):
        return [s.name for s in sorted(self.storage_dir.glob("*"), reverse=True)]

    def _prune(self):
        snapshots = sorted(self.storage_dir.glob("*"))
        while len(snapshots) > self.max_snapshots:
            shutil.rmtree(snapshots.pop(0))
