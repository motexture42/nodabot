# Main Agent Reasoning Loop with Resilience
import json
import re
import logging
import threading
import time
import tiktoken
from .llm import LLMProvider
from .memory import SessionManager
from config import Config
from utils.snapshot import SnapshotManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MicroAgent")

class Agent:
    """
    Orchestrates the reasoning-action loop. 
    Includes advanced resilience: error diagnosis and strategy pivoting.
    """
    def __init__(self, tools: list = None, session_id: str = "main", emit_cb=None, name="Main"):
        self.llm = LLMProvider()
        self.memory = SessionManager(storage_dir=Config.SESSIONS_DIR)
        self.snapshot_mgr = SnapshotManager()
        self.session_id = session_id
        self.tools = tools or []
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.emit_cb = emit_cb
        self.name = name
        self.lock = threading.Lock()
        
        # State & Heartbeat
        self.current_mission = None
        self.next_planned_step = None
        self.is_busy = False
        
        # Resilience State
        self.consecutive_failures = 0
        self.failure_threshold = 3
        self.is_debugging = False
        
        # Knowledge Base Link
        self.kb = self.tool_map.get("knowledge_base")
        
        # Load existing history or start fresh
        loaded_history = self.memory.load(self.session_id)
        if loaded_history:
            self.history = loaded_history
            logger.info(f"Loaded session {self.session_id} with {len(self.history)} messages.")
        else:
            self.history = [
                {"role": "system", "content": """You are NodaBot (NB), a high-precision autonomous system. 

DISCIPLINE RULES:
1. NO META-COMMENTARY: Do NOT include 'MISSION:', 'NEXT_STEP:', or technical tool details in your final responses or in 'send_user_message'.
2. RESULTS ONLY: Deliver results directly. If a user asks for a file, create it and report success.
3. MESSAGING: Use 'send_user_message' to talk to the user during jobs/missions. 
4. STATE: You MUST include 'MISSION: <goal>', 'NEXT_STEP: <action>', or 'MISSION_COMPLETE' at the END of your internal reasoning (assistant messages), but these will be filtered from the user.
5. RESILIENCE: If a tool fails, analyze the error and try a DIFFERENT approach."""}
            ]
            logger.info(f"Started new session {self.session_id}.")

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    def _clean_content(self, content: str) -> str:
        if not content: return ""
        # 1. Remove reasoning tags
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # 2. Aggressively remove internal state labels and meta-commentary patterns
        patterns = [
            r'(?i)MISSION:.*?(?=\n|$)', 
            r'(?i)NEXT_STEP:.*?(?=\n|$)', 
            r'(?i)NEXT_STEP\s*\(.*?\):.*?(?=\n|$)',
            r'(?i)MISSION_COMPLETE',
            r'(?i)TOOL_CALL DETAILS:.*?(?=\n|$)',
            r'(?i)TOOL_CALL\s*->.*?(?=\n|$)',
            r'(?i)File operation:.*?(?=\n|$)',
            r'(?i)Scope:.*?(?=\n|$)',
            r'(?i)Destructive impact:.*?(?=\n|$)',
            r'(?i)Backup/snapshot:.*?(?=\n|$)',
            r'(?i)Execution:.*?(?=\n|$)',
            r'(?i)action:.*?(?=\n|$)',
            r'(?i)file_path:.*?(?=\n|$)'
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned)
        
        return cleaned.strip()

    def _count_tokens(self, text: str) -> int:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.debug(f"Token count error: {e}")
            return len(text) // 4

    def _prune_history(self, max_tokens: int = 8000):
        total_tokens = sum(self._count_tokens(str(m.get("content", ""))) for m in self.history)
        if total_tokens > max_tokens and len(self.history) > 10:
            logger.info(f"Pruning history (tokens: {total_tokens} > {max_tokens})")
            for i in range(1, len(self.history) - 5):
                if self.history[i].get("role") == "tool" and self.history[i].get("content") != "(Old tool output removed)":
                    self.history[i]["content"] = "(Old tool output removed)"
                    break

    def _reflect(self, last_response: dict) -> str:
        """Internal critic to review the proposed action/plan."""
        content = last_response.get("content", "")
        tool_calls = last_response.get("tool_calls", [])
        
        if not content and not tool_calls: return None
        
        reflection_prompt = (
            "SYSTEM: You are the 'Internal Critic' for an autonomous agent. "
            "Evaluate the agent's proposed MISSION and NEXT_STEP or TOOL_CALL.\n\n"
            "CRITERIA:\n"
            "1. LOGIC: Is the next step the most efficient path to the mission?\n"
            "2. SAFETY: Is the action dangerous or irreversible without a snapshot?\n"
            "3. REDUNDANCY: Is the agent repeating a failed action?\n\n"
            f"PROPOSED ACTION:\n{content}\nTools: {[t['function']['name'] for t in tool_calls]}\n\n"
            "TASK: If the plan is solid and logical, reply ONLY with 'APPROVED'. "
            "If flawed, provide a concise 'CRITICISM' and a 'SUGGESTED_FIX'. "
            "Be extremely brief and do not explain yourself if approving."
        )
        
        try:
            res = self.llm.chat_completion([{"role": "user", "content": reflection_prompt}], tools=None)
            criticism = self._clean_content(res.get("content", ""))
            if "APPROVED" in criticism.upper() and len(criticism) < 20:
                return None
            return criticism
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return None

    def _consolidate_memory(self, turn_history: list):
        if not self.kb: return
        interaction = "\n".join([f"{m['role']}: {m.get('content','')[:500]}" for m in turn_history if m.get('content')])
        prompt = (
            "SYSTEM: Extract only important facts/preferences from this interaction. "
            "Format: ULTRA-CONCISE bullets. If nothing worth remembering, reply 'SKIP'.\n\n"
            f"INTERACTION:\n{interaction}"
        )
        try:
            res = self.llm.chat_completion([{"role": "user", "content": prompt}], tools=None)
            summary = self._clean_content(res.get("content", ""))
            if summary and "SKIP" not in summary.upper():
                self.kb.run(action="store", text=summary, metadata=f"session_{self.session_id}")
                self._emit("system_msg", {"message": "🧠 Memory consolidated."})
                logger.info("Memory consolidated into knowledge base.")
        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")

    def _trigger_debugger(self, error_msg: str):
        """Internal sub-agent logic to diagnose a persistent failure."""
        self.is_debugging = True
        logger.warning(f"Debugger triggered after {self.consecutive_failures} failures. Last error: {error_msg}")
        self._emit("system_msg", {"message": "🛠 Entering Debug Mode: Diagnosing persistent failures..."})
        
        diagnosis_prompt = (
            "SYSTEM: You are a specialized Debugger Agent. "
            f"CONTEXT: The main agent has failed {self.consecutive_failures} times. "
            f"LAST ERROR: {error_msg}\n\n"
            "TASK: Analyze the history and error. Provide a NEW STRATEGY that avoids this error. "
            "Suggest alternative tools or a different logical path. Be extremely technical."
        )
        
        try:
            res = self.llm.chat_completion([{"role": "user", "content": diagnosis_prompt}], tools=None)
            strategy = self._clean_content(res.get("content", "Try a different approach."))
            self.history.append({"role": "system", "content": f"DEBUGGER RECOMMENDATION: {strategy}\nABANDON CURRENT PATH. START NEW STRATEGY NOW."})
            self._emit("system_msg", {"message": "✅ Debugger suggested new strategy. Pivoting..."})
            logger.info("Debugger provided new strategy.")
            self.consecutive_failures = 0 
        except Exception as e:
            logger.error(f"Debugger failed: {e}")
        finally:
            self.is_debugging = False

    def heartbeat(self):
        if self.is_busy: return
        with self.lock:
            scheduler = self.tool_map.get("manage_jobs")
            if scheduler:
                now = time.time()
                for jid, job in list(scheduler.jobs.items()):
                    if now >= job["next_run"]:
                        job["runs_completed"] = job.get("runs_completed", 0) + 1
                        should_remove = (job.get("max_runs", 0) > 0 and job["runs_completed"] >= job["max_runs"])
                        self._emit("system_msg", {"message": f"⚡ Running job: {job['task']}"})
                        logger.info(f"Running scheduled job {jid}: {job['task']}")
                        job["last_run"], job["next_run"] = now, now + job["interval"]
                        if should_remove: scheduler.run(action="remove", job_id=jid)
                        else: scheduler._save_jobs()
                        self._emit("jobs_update", {"jobs": scheduler.jobs})
                        threading.Thread(target=lambda: self.run(f"COMMAND: Execute scheduled task: '{job['task']}'. Use 'send_user_message'. No commentary.", is_internal=True)).start()
                        return 
            
            if self.current_mission:
                logger.debug(f"Heartbeat: Continuing mission '{self.current_mission}'")
                self._emit("system_msg", {"message": "💓 Heartbeat: Mission sync..."})
                threading.Thread(target=lambda: self.run(f"COMMAND: Continue mission '{self.current_mission}'. Current: {self.next_planned_step}. Execute next action.", is_internal=True)).start()

    def run(self, user_prompt: str, is_internal: bool = False):
        self.is_busy = True
        try:
            if user_prompt.strip() in ["/new", "/reset"]:
                logger.info(f"Resetting session {self.session_id}")
                self.history = [self.history[0]]
                self.current_mission = self.next_planned_step = None
                self.consecutive_failures = 0
                self.memory.save(self.session_id, self.history)
                s = self.tool_map.get("manage_jobs"); 
                if s: s.jobs = {}; s._save_jobs()
                self._emit("jobs_update", {"jobs": {}})
                self._emit("system_msg", {"message": "Session reset."})
                return "System reset."

            if not is_internal: 
                self._emit("chat_message", {"role": "user", "content": user_prompt})
                logger.info(f"User message: {user_prompt[:50]}...")

            if self.kb and not is_internal:
                try:
                    past_context = self.kb.run(action="search", text=user_prompt)
                    if "Found relevant snippets" in past_context:
                        if self.history and self.history[0]["role"] == "system":
                            self.history[0]["content"] += f"\n\nPAST CONTEXT:\n{past_context}"
                        else:
                            self.history.insert(0, {"role": "system", "content": f"PAST CONTEXT:\n{past_context}"})
                except Exception as e:
                    logger.error(f"Knowledge base search failed: {e}")

            self.history.append({"role": "user", "content": user_prompt})
            self._emit("agent_start", {"agent": self.name, "task": user_prompt[:100] + "..."})
            turn_history_start_idx = len(self.history) - 1

            for turn in range(Config.MAX_TURNS):
                self._emit("turn_update", {"agent": self.name, "turn": turn + 1})
                self._prune_history()
                
                self._emit("agent_status", {"agent": self.name, "status": "thinking"})
                try:
                    response = self.llm.chat_completion(self.history, tools=self.tools)
                except Exception as e:
                    logger.error(f"LLM call failed: {e}")
                    break
                
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", [])

                # 1. APPEND ASSISTANT RESPONSE FIRST (Standard Protocol)
                self.history.append(response)

                # 2. REFLECTION STEP
                reflection = None
                critical_tool = any(t["function"]["name"] in ["execute_shell", "file_manager"] for t in tool_calls)
                if self.consecutive_failures > 0 or critical_tool:
                    self._emit("agent_status", {"agent": self.name, "status": "reflecting"})
                    reflection = self._reflect(response)
                
                if reflection:
                    logger.info(f"Reflection triggered: {reflection}")
                    if tool_calls:
                        # Protocol: Must respond to tool calls
                        for call in tool_calls:
                            self.history.append({
                                "role": "tool",
                                "tool_call_id": call.get("id", "0"),
                                "name": call["function"]["name"],
                                "content": f"CRITIC FEEDBACK: {reflection}. Strategy rejected. Try again."
                            })
                    else:
                        # No tools, just append user feedback
                        self.history.append({"role": "user", "content": f"__INTERNAL_FEEDBACK__: {reflection}\nPlease correct your response."})
                    continue # Start next turn with the feedback in history

                # MISSION Tracking
                if "MISSION:" in content: 
                    self.current_mission = content.split("MISSION:")[1].split("\n")[0].strip()
                if "NEXT_STEP:" in content: 
                    self.next_planned_step = content.split("NEXT_STEP:")[1].split("\n")[0].strip()
                if "MISSION_COMPLETE" in content: 
                    logger.info("Mission Completed.")
                    self.current_mission = self.next_planned_step = None
                    browser_tool = self.tool_map.get("browser_controller")
                    if browser_tool: threading.Thread(target=lambda: browser_tool.run(action="close")).start()

                self._emit("mission_update", {"mission": self.current_mission, "next_step": self.next_planned_step})
                
                if not tool_calls:
                    if content.strip() and not is_internal:
                        self._emit("agent_reply", {"agent": self.name, "content": self._clean_content(content)})
                    break

                for call in tool_calls:
                    tool_name = call["function"]["name"]
                    try:
                        tool_args = json.loads(call["function"]["arguments"])
                    except Exception as e:
                        logger.error(f"Failed to parse arguments for {tool_name}: {e}")
                        obs = f"Error: Invalid JSON arguments."
                        self.history.append({"role": "tool", "tool_call_id": call.get("id", "0"), "name": tool_name, "content": obs})
                        continue

                    self._emit("agent_status", {"agent": self.name, "status": "executing", "tool": tool_name, "args": tool_args})
                    self._emit("tool_start", {"agent": self.name, "tool": tool_name, "args": tool_args})
                    
                    tool = self.tool_map.get(tool_name)
                    try:
                        if tool: tool.pre_run(snapshot_mgr=self.snapshot_mgr, **tool_args)
                        run_args = tool_args.copy()
                        run_args['snapshot_mgr'] = self.snapshot_mgr
                        obs = tool.run(**run_args) if tool else f"Error: {tool_name} not found."
                        if tool: tool.post_run(obs, snapshot_mgr=self.snapshot_mgr, **tool_args)
                    except Exception as e:
                        logger.error(f"Tool execution failed ({tool_name}): {e}")
                        obs = f"Error: {str(e)}"
                    
                    if "Error" in str(obs) or "failed" in str(obs).lower():
                        self.consecutive_failures += 1
                        if self.consecutive_failures >= self.failure_threshold: self._trigger_debugger(str(obs))
                    else:
                        self.consecutive_failures = 0 
                    
                    if tool_name == "send_user_message": 
                        cleaned_msg = self._clean_content(tool_args.get("message", ""))
                        if cleaned_msg: self._emit("agent_reply", {"agent": self.name, "content": cleaned_msg})
                    if tool_name == "manage_jobs": self._emit("jobs_update", {"jobs": tool.jobs})

                    self._emit("tool_end", {"agent": self.name, "tool": tool_name, "result": obs})
                    self.history.append({"role": "tool", "tool_call_id": call.get("id", "0"), "name": tool_name, "content": obs})
            
            if not is_internal: self._consolidate_memory(self.history[turn_history_start_idx:])
            self._emit("agent_end", {"agent": self.name, "status": "success"})
            self.memory.save(self.session_id, self.history)
            return content
        except Exception as e:
            logger.exception("Agent run error")
            return f"Agent Error: {str(e)}"
        finally: 
            self._emit("agent_status", {"agent": self.name, "status": "idle"})
            self.is_busy = False
