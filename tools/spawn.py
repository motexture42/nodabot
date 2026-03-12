# Child Agent Spawning Tool - Swarm Teamwork
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from .base import BaseTool

class SpawnTool(BaseTool):
    """
    Spawns specialized child agents to execute complex sub-tasks.
    Supports running them sequentially (sharing state) or in parallel (for speed).
    """
    def __init__(self, tools_factory=None, emit_cb=None):
        self.tools_factory = tools_factory
        self.emit_cb = emit_cb

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str:
        return "spawn_child_agent"

    @property
    def description(self) -> str:
        return (
            "CRITICAL for complex tasks: Use this to delegate work to specialized sub-agents. "
            "Act as a PROJECT MANAGER. Spawn a Researcher, Coder, Writer, or QA expert. "
            "You can run them in 'parallel' for speed (e.g. researching 3 different things at once) "
            "or 'sequential' if one agent needs the output of the previous agent."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string", 
                    "enum": ["sequential", "parallel"],
                    "description": "How to execute the tasks."
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "Instruction for this specific step."},
                            "role": {"type": "string", "description": "Role: researcher, coder, writer, qa."}
                        },
                        "required": ["task", "role"]
                    }
                }
            },
            "required": ["tasks", "mode"]
        }

    def _run_single(self, task: str, role: str, blackboard: str = "") -> str:
        from core.agent import Agent
        import uuid
        
        session_id = f"swarm-{role.lower()}-{str(uuid.uuid4())[:4]}"
        child_name = f"{role.capitalize()} Agent"
        all_tools = self.tools_factory() if self.tools_factory else []
        
        # Scope tools by persona for safety and modularity
        allowed_tools = {
            "researcher": ["web_search", "fetch_url", "browser_controller", "knowledge_base"],
            "coder": ["local_terminal", "file_manager", "execute_python", "knowledge_base"],
            "writer": ["file_manager", "knowledge_base"],
            "qa": ["local_terminal", "file_manager", "execute_python", "knowledge_base", "browser_controller", "web_search"]
        }
        
        child_tools = all_tools
        if role.lower() in allowed_tools:
            allowed = allowed_tools[role.lower()]
            child_tools = [t for t in all_tools if t.name in allowed]
        
        self._emit("agent_start", {"agent": child_name, "task": task})
        
        child_agent = Agent(tools=child_tools, session_id=session_id, emit_cb=self.emit_cb, name=child_name)
        
        role_prompts = {
            "researcher": "You are an autonomous Researcher. Gather verified facts using your tools.",
            "coder": "You are an autonomous Coder. Write and test code. Use data provided.",
            "writer": "You are an autonomous Writer. Format and summarize data into high-quality text.",
            "qa": "You are an autonomous QA/Critic. Test and find flaws in the work."
        }
        
        context_msg = f"\nTEAM BOARD (Context):\n{blackboard}" if blackboard else ""
        sys_msg = role_prompts.get(role.lower(), f"You are an autonomous {role}.")
        
        # Override the child agent's system prompt
        child_agent.history[0]["content"] = f"{sys_msg}{context_msg}\n\nTask: {task}\nBe completely autonomous. Execute tools until the task is complete, then provide your final report."

        try:
            result = child_agent.run(task, is_internal=True)
            self._emit("agent_end", {"agent": child_name, "status": "success"})
            return f"### {role.upper()} AGENT RESULT:\n{result}"
        except Exception as e:
            self._emit("agent_end", {"agent": child_name, "status": "error"})
            return f"### {role.upper()} AGENT ERROR: {str(e)}"

    def run(self, **kwargs) -> str:
        tasks = kwargs.get("tasks", [])
        mode = kwargs.get("mode", "sequential")
        
        if not tasks: return "Error: No tasks provided."

        results = []
        
        if mode == "sequential":
            blackboard = ""
            for t in tasks:
                res = self._run_single(t["task"], t["role"], blackboard)
                results.append(res)
                blackboard += f"\n{res}\n"
        else:
            # Parallel mode
            with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as executor:
                futures = []
                for t in tasks:
                    futures.append(executor.submit(self._run_single, t["task"], t["role"], ""))
                
                for future in futures:
                    results.append(future.result())

        return "\n\n---\n\n".join(results)
