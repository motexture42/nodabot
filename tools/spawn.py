# Child Agent Spawning Tool - Pure Sequential Teamwork
import json
from .base import BaseTool

class SpawnTool(BaseTool):
    """
    Spawns specialized child agents in a sequential chain.
    Each agent sees the results of all previous agents in the chain.
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
            "Instead of doing everything yourself, act as a PROJECT MANAGER. "
            "Spawn a Researcher, Coder, Writer, or QA expert. "
            "This avoids context-window limits and produces higher-quality, verified results. "
            "Each agent in the list will run sequentially, passing their findings to the next."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
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
            "required": ["tasks"]
        }

    def _run_single(self, task: str, role: str, blackboard: str = "") -> str:
        from core.agent import Agent
        session_id = f"swarm-{role.lower()}"
        child_name = f"{role.capitalize()} Agent"
        child_tools = self.tools_factory() if self.tools_factory else []
        
        self._emit("agent_start", {"agent": child_name, "task": task})
        
        child_agent = Agent(tools=child_tools, session_id=session_id, emit_cb=self.emit_cb, name=child_name)
        
        role_prompts = {
            "researcher": "You are a Researcher. Gather verified facts using tools.",
            "coder": "You are a Coder. Write and test code. Use data from previous agents.",
            "writer": "You are a Writer. Format and summarize data into high-quality text.",
            "qa": "You are a QA/Critic. Test and find flaws in the work done so far."
        }
        
        context_msg = f"\nTEAM BOARD (Results from previous steps):\n{blackboard}" if blackboard else ""
        sys_msg = role_prompts.get(role.lower(), f"You are a specialized {role}.")
        child_agent.history[0]["content"] = f"{sys_msg}{context_msg}\n\nTask: {task}\nBe concise. Complete your task and report back."

        try:
            result = child_agent.run(task, is_internal=True)
            self._emit("agent_end", {"agent": child_name, "status": "success"})
            return f"### {role.upper()} AGENT RESULT:\n{result}"
        except Exception as e:
            self._emit("agent_end", {"agent": child_name, "status": "error"})
            return f"### {role.upper()} AGENT ERROR: {str(e)}"

    def run(self, **kwargs) -> str:
        tasks = kwargs.get("tasks", [])
        if not tasks: return "Error: No tasks."

        blackboard = ""
        results = []
        
        print(f"[>>>] Swarm: Sequential Chain Started ({len(tasks)} steps)")
        
        for t in tasks:
            res = self._run_single(t["task"], t["role"], blackboard)
            results.append(res)
            # Carry result forward to the next agent
            blackboard += f"\n{res}\n"

        return "\n\n---\n\n".join(results)
