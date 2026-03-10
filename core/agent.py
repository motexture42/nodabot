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
        self.queue_count = 0
        
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
            self._init_history()

    def _init_history(self):
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
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
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
        except: return len(text) // 4

    def _prune_history(self, max_tokens: int = 8000):
        total_tokens = sum(self._count_tokens(str(m.get("content", ""))) for m in self.history)
        if total_tokens > max_tokens and len(self.history) > 10:
            for i in range(1, len(self.history) - 5):
                if self.history[i].get("role") == "tool" and self.history[i].get("content") != "(Old tool output removed)":
                    self.history[i]["content"] = "(Old tool output removed)"
                    break

    def _reflect(self, last_response: dict) -> str:
        content = last_response.get("content", "")
        tool_calls = last_response.get("tool_calls", [])
        if not content and not tool_calls: return None
        reflection_prompt = (
            "SYSTEM: You are the 'Internal Critic'. Evaluate the plan.\n"
            f"PROPOSED ACTION:\n{content}\nTools: {[t['function']['name'] for t in tool_calls]}\n\n"
            "TASK: Reply ONLY with 'APPROVED' or provide a concise 'CRITICISM' and 'SUGGESTED_FIX'."
        )
        try:
            res = self.llm.chat_completion([{"role": "user", "content": reflection_prompt}], tools=None)
            criticism = self._clean_content(res.get("content", ""))
            if "APPROVED" in criticism.upper() and len(criticism) < 20: return None
            return criticism
        except: return None

    def _trigger_debugger(self, error_msg: str):
        self.is_debugging = True
        self._emit("system_msg", {"message": "🛠 Entering Debug Mode..."})
        prompt = f"SYSTEM: Debugger. Last error: {error_msg}. Suggest new strategy."
        try:
            res = self.llm.chat_completion([{"role": "user", "content": prompt}], tools=None)
            strategy = self._clean_content(res.get("content", "Try another way."))
            self.history.append({"role": "system", "content": f"DEBUGGER: {strategy}"})
            self.consecutive_failures = 0 
        finally: self.is_debugging = False

    def heartbeat(self):
        if self.is_busy: return
        with self.lock:
            scheduler = self.tool_map.get("manage_jobs")
            if scheduler:
                now = time.time()
                for jid, job in list(scheduler.jobs.items()):
                    if now >= job["next_run"]:
                        self._emit("system_msg", {"message": f"⚡ Running job: {job['task']}"})
                        job["last_run"], job["next_run"] = now, now + job["interval"]
                        scheduler._save_jobs()
                        threading.Thread(target=lambda: self.run(f"COMMAND: Execute job: '{job['task']}'", is_internal=True)).start()
                        return 
            if self.current_mission:
                threading.Thread(target=lambda: self.run(f"COMMAND: Continue mission '{self.current_mission}'", is_internal=True)).start()

    def run(self, user_prompt: str, is_internal: bool = False):
        # 1. IMMEDIATE UI FEEDBACK (Outside Lock)
        if not is_internal:
            self._emit("chat_message", {"role": "user", "content": user_prompt})
            self.queue_count += 1
            if self.queue_count > 1:
                self._emit("system_msg", {"message": f"🕒 Queued ({self.queue_count-1} ahead)"})
            self._emit("queue_update", {"count": self.queue_count})

        # 2. ACQUIRE LOCK (Sequential processing starts here)
        self.lock.acquire()
        self.is_busy = True
        try:
            if not is_internal:
                self.queue_count = max(0, self.queue_count - 1)
                self._emit("queue_update", {"count": self.queue_count})

            if user_prompt.strip() in ["/new", "/reset"]:
                self._init_history()
                self.current_mission = self.next_planned_step = None
                self.consecutive_failures = 0
                self.memory.save(self.session_id, self.history)
                return "Reset."

            # Protocol Check: If last message was an assistant tool_call, we MUST fix history before adding USER message
            if self.history and self.history[-1].get("role") == "assistant" and self.history[-1].get("tool_calls"):
                logger.warning("Protocol violation detected: Last message was tool_call without response. Cleaning...")
                for call in self.history[-1]["tool_calls"]:
                    self.history.append({"role": "tool", "tool_call_id": call.get("id"), "name": call["function"]["name"], "content": "Error: Interrupted by user."})

            self.history.append({"role": "user", "content": user_prompt})
            self._emit("agent_start", {"agent": self.name, "task": user_prompt[:50]})

            for turn in range(Config.MAX_TURNS):
                self._emit("turn_update", {"agent": self.name, "turn": turn + 1})
                self._prune_history()
                self._emit("agent_status", {"agent": self.name, "status": "thinking"})
                
                try:
                    response = self.llm.chat_completion(self.history, tools=self.tools)
                except Exception as e:
                    logger.error(f"LLM Error: {e}")
                    break
                
                content = response.get("content", "") or ""
                
                # Check for error in response dictionary (from LLMProvider.chat_completion catch block)
                if "LLM Error" in content:
                    if not is_internal:
                        self._emit("agent_reply", {"agent": self.name, "content": f"⚠️ {content}"})
                    break

                tool_calls = response.get("tool_calls", [])

                # 3. REFLECTION
                reflection = None
                if any(t["function"]["name"] in ["execute_shell", "file_manager"] for t in tool_calls):
                    self._emit("agent_status", {"agent": self.name, "status": "reflecting"})
                    reflection = self._reflect(response)
                
                if reflection:
                    self.history.append(response)
                    if tool_calls:
                        for call in tool_calls:
                            self.history.append({"role": "tool", "tool_call_id": call.get("id"), "name": call["function"]["name"], "content": f"CRITIC: {reflection}"})
                    else:
                        self.history.append({"role": "user", "content": f"__INTERNAL_FEEDBACK__: {reflection}"})
                    continue 

                # 4. COMMIT RESPONSE
                self.history.append(response)

                if "MISSION:" in content: self.current_mission = content.split("MISSION:")[1].split("\n")[0].strip()
                if "MISSION_COMPLETE" in content:
                    self.current_mission = None
                    logger.info("Mission Completed. Browser remains open for further interaction.")

                if not tool_calls:
                    if content.strip() and not is_internal:
                        self._emit("agent_reply", {"agent": self.name, "content": self._clean_content(content)})
                    break

                # 5. EXECUTE TOOLS
                for call in tool_calls:
                    tool_name = call["function"]["name"]
                    try: tool_args = json.loads(call["function"]["arguments"])
                    except: continue

                    self._emit("agent_status", {"agent": self.name, "status": "executing", "tool": tool_name, "args": tool_args})
                    self._emit("tool_start", {"agent": self.name, "tool": tool_name, "args": tool_args})
                    tool = self.tool_map.get(tool_name)
                    try:
                        if tool: tool.pre_run(snapshot_mgr=self.snapshot_mgr, **tool_args)
                        run_args = tool_args.copy()
                        run_args['snapshot_mgr'] = self.snapshot_mgr
                        obs = tool.run(**run_args) if tool else "Error: Not found."
                        if tool: tool.post_run(obs, snapshot_mgr=self.snapshot_mgr, **tool_args)
                    except Exception as e: obs = f"Error: {e}"
                    
                    if "Error" in str(obs): self.consecutive_failures += 1
                    else: self.consecutive_failures = 0 
                    
                    if tool_name == "send_user_message": 
                        self._emit("agent_reply", {"agent": self.name, "content": self._clean_content(tool_args.get("message", ""))})

                    self._emit("tool_end", {"agent": self.name, "tool": tool_name, "result": obs})
                    self.history.append({"role": "tool", "tool_call_id": call.get("id"), "name": tool_name, "content": obs})
            
            self.memory.save(self.session_id, self.history)
            return content
        finally: 
            self._emit("agent_status", {"agent": self.name, "status": "idle"})
            self.is_busy = False
            self.lock.release()
