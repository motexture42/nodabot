# Session Management for Persistence
import json
import os
from pathlib import Path

class SessionManager:
    """
    Handles saving and loading session history to/from disk.
    """
    def __init__(self, storage_dir: str = "sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    def save(self, session_id: str, history: list):
        """Save a list of messages to a JSON file."""
        path = self._get_path(session_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

    def load(self, session_id: str) -> list:
        """Load history from a JSON file. Returns None if not found."""
        path = self._get_path(session_id)
        if not path.exists():
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_sessions(self) -> list:
        """Return a list of all existing session IDs."""
        return [f.stem for f in self.storage_dir.glob("*.json")]

    def delete(self, session_id: str):
        """Remove a session file."""
        path = self._get_path(session_id)
        if path.exists():
            path.unlink()
