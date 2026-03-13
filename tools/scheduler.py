from tools.base import BaseTool
import json
import time
import os
from pathlib import Path

class SchedulerTool(BaseTool):
    """Allows the agent to schedule tasks to run in the future or periodically."""
    
    def __init__(self, agent_instance=None):
        self.agent = agent_instance
        self.persistence_file = Path("sessions/jobs.json")
        self.jobs = self._load_jobs()

    def _load_jobs(self):
        """Load jobs from disk."""
        if self.persistence_file.exists():
            try:
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading jobs: {e}")
        return {}

    def _save_jobs(self):
        """Save jobs to disk."""
        try:
            self.persistence_file.parent.mkdir(exist_ok=True)
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, indent=2)
        except Exception as e:
            print(f"Error saving jobs: {e}")

    @property
    def name(self) -> str:
        return "manage_jobs"

    @property
    def description(self) -> str:
        return "Schedules a task to run later or at a recurring interval. Use this to automate monitoring, reporting, or long-running workflows. If the user asks for a ONE-TIME reminder or delay, you MUST set max_runs=1."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "list"],
                    "description": "The action to perform on the job queue."
                },
                "task": {
                    "type": "string",
                    "description": "The specific instruction or goal for the job (e.g. 'Check the weather and report back')."
                },
                "interval_seconds": {
                    "type": "integer",
                    "description": "How often to run the task, or the delay before it runs."
                },
                "max_runs": {
                    "type": "integer",
                    "description": "How many times to run the job. Set to 1 for a one-time delayed task. Set to 0 or omit for forever."
                },
                "job_id": {
                    "type": "string",
                    "description": "A unique identifier for the job."
                }
            },
            "required": ["action"]
        }

    def run(self, action: str, task: str = None, interval_seconds: int = 60, max_runs: int = 0, job_id: str = None, **kwargs) -> str:
        if action == "add":
            if not task: return "Error: 'task' is required."
            jid = job_id or f"job_{int(time.time())}"
            now = time.time()
            self.jobs[jid] = {
                "task": task,
                "interval": interval_seconds,
                "last_run": 0,
                "next_run": now + interval_seconds,
                "status": "scheduled",
                "max_runs": max_runs,
                "runs_completed": 0
            }
            self._save_jobs()
            limit_text = f"{max_runs} times" if max_runs > 0 else "forever"
            return f"Successfully scheduled job '{jid}': '{task}' every {interval_seconds}s, running {limit_text}."
            
        elif action == "remove":
            if not job_id or job_id not in self.jobs:
                return f"Error: Job ID '{job_id}' not found."
            del self.jobs[job_id]
            self._save_jobs()
            return f"Job '{job_id}' removed."
            
        elif action == "list":
            if not self.jobs: return "No active jobs."
            return json.dumps(self.jobs, indent=2)
            
        return "Unknown action."
