# Child Agent Spawning Tool - Sequential Teamwork and Multi-Agent Debate
import json
import threading
import uuid
import queue
from .base import BaseTool
from core.bus import MessageBus

class SendMessageTool(BaseTool):
    def __init__(self, bus: MessageBus, sender_name: str):
        self.bus = bus
        self.sender_name = sender_name

    @property
    def name(self) -> str:
        return "send_message"

    @property
    def description(self) -> str:
        return "Send a message to another agent or broadcast to everyone on the bus."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Name of the agent (e.g., 'Coder Agent', 'QA Agent') or 'broadcast'."},
                "message": {"type": "string", "description": "The message to send."}
            },
            "required": ["target", "message"]
        }

    def run(self, **kwargs) -> str:
        target = kwargs.get("target")
        message = kwargs.get("message")
        self.bus.publish(self.sender_name, target, message)
        return f"Message successfully sent to {target}."

class FinishDebateTool(BaseTool):
    def __init__(self, bus: MessageBus):
        self.bus = bus

    @property
    def name(self) -> str:
        return "finish_debate"

    @property
    def description(self) -> str:
        return "Call this to end the multi-agent debate when the goal has been fully achieved."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "A comprehensive summary of the final achieved result."}
            },
            "required": ["summary"]
        }

    def run(self, **kwargs) -> str:
        summary = kwargs.get("summary")
        self.bus.finish(summary)
        return "Debate marked as finished."

class SpawnTool(BaseTool):
    """
    Spawns specialized child agents either in a sequential chain or in a collaborative debate chat room.
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
            "You can choose 'sequential' mode for step-by-step execution, or 'debate' mode "
            "where agents join a shared chat bus to collaborate iteratively until the task is complete."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["sequential", "debate"],
                    "description": "Execution mode. 'sequential' runs agents one after another. 'debate' puts them in a shared chat room."
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "Instruction for this specific step or the initial prompt for this agent."},
                            "role": {"type": "string", "description": "Role: researcher, coder, writer, qa."}
                        },
                        "required": ["task", "role"]
                    }
                }
            },
            "required": ["mode", "tasks"]
        }

    def _run_single(self, task: str, role: str, blackboard: str = "") -> str:
        from core.agent import Agent
        session_id = f"swarm-{role.lower()}-{str(uuid.uuid4())[:4]}"
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
        
        child_agent.history[0]["content"] += f"\n\n--- SUB-AGENT DIRECTIVE ---\n{sys_msg}{context_msg}\n\nTask: {task}\nCRITICAL: Be completely autonomous. You MUST NOT ask the user for input. You MUST NOT use `spawn_child_agent` yourself. Execute tools until the task is complete, then provide your final report."

        try:
            result = child_agent.run(task, is_internal=True)
            self._emit("agent_end", {"agent": child_name, "status": "success"})
            return f"### {role.upper()} AGENT RESULT:\n{result}"
        except Exception as e:
            self._emit("agent_end", {"agent": child_name, "status": "error"})
            return f"### {role.upper()} AGENT ERROR: {str(e)}"

    def _agent_bus_worker(self, agent, bus, initial_task):
        q = bus.subscribe(agent.name)
        
        # Initial run with task
        try:
            agent.run(f"INITIAL DIRECTIVE: {initial_task}", is_internal=True)
        except Exception as e:
            print(f"Error in {agent.name} initial run: {e}")
            
        while not bus.is_finished():
            try:
                # Wait for a message with a 2-second timeout so it checks finish flag
                msg = q.get(timeout=2)
                prompt = msg["formatted_msg"]
                agent.run(prompt, is_internal=True)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in {agent.name} bus loop: {e}")
                
        self._emit("agent_end", {"agent": agent.name, "status": "success"})

    def _run_debate(self, tasks: list) -> str:
        from core.agent import Agent
        bus = MessageBus()
        threads = []
        
        print(f"[>>>] Swarm: Debate Mode Started ({len(tasks)} agents)")
        
        # Instantiate and start agents
        for t in tasks:
            role = t["role"]
            task = t["task"]
            session_id = f"swarm-{role.lower()}-{str(uuid.uuid4())[:4]}"
            child_name = f"{role.capitalize()} Agent"
            
            # Agent needs standard tools + bus tools
            child_tools = self.tools_factory() if self.tools_factory else []
            child_tools.append(SendMessageTool(bus, child_name))
            child_tools.append(FinishDebateTool(bus))
            
            self._emit("agent_start", {"agent": child_name, "task": f"Joined Debate: {task}"})
            child_agent = Agent(tools=child_tools, session_id=session_id, emit_cb=self.emit_cb, name=child_name)
            
            role_prompts = {
                "researcher": "You are a Researcher. Gather verified facts using tools.",
                "coder": "You are a Coder. Write and test code.",
                "writer": "You are a Writer. Format and summarize data into high-quality text.",
                "qa": "You are a QA/Critic. Test and find flaws in the work done so far."
            }
            sys_msg = role_prompts.get(role.lower(), f"You are a specialized {role}.")
            
            child_agent.history[0]["content"] += (
                f"\n\n--- SUB-AGENT DEBATE DIRECTIVE ---\n{sys_msg}\n"
                f"You are part of a multi-agent debate. You can communicate with other agents using `send_message`.\n"
                f"If the overall goal has been met by the team, use `finish_debate`.\n"
                f"CRITICAL: Be completely autonomous. You MUST NOT ask the user for input. "
                f"You MUST NOT use `spawn_child_agent` yourself."
            )
            
            worker_thread = threading.Thread(target=self._agent_bus_worker, args=(child_agent, bus, task))
            worker_thread.start()
            threads.append(worker_thread)
            
        # Wait for the debate to finish (one of the agents calls finish_debate)
        final_summary = bus.wait_until_finished()
        
        for thread in threads:
            thread.join(timeout=2)
            
        return f"### DEBATE FINAL SUMMARY:\n{final_summary}"

    def run(self, **kwargs) -> str:
        tasks = kwargs.get("tasks", [])
        mode = kwargs.get("mode", "sequential")
        
        if not tasks: return "Error: No tasks."

        if mode == "debate":
            return self._run_debate(tasks)

        # Sequential mode fallback
        blackboard = ""
        results = []
        print(f"[>>>] Swarm: Sequential Chain Started ({len(tasks)} steps)")
        for t in tasks:
            res = self._run_single(t["task"], t["role"], blackboard)
            results.append(res)
            blackboard += f"\n{res}\n"

        return "\n\n---\n\n".join(results)
