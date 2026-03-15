import queue
import threading
import time

class MessageBus:
    def __init__(self):
        self.subscribers = {}
        self.history = []
        self.lock = threading.Lock()
        self._finished = threading.Event()
        self.final_result = ""

    def subscribe(self, agent_name: str) -> queue.Queue:
        with self.lock:
            if agent_name not in self.subscribers:
                self.subscribers[agent_name] = queue.Queue()
            return self.subscribers[agent_name]

    def publish(self, sender: str, target: str, message: str):
        with self.lock:
            msg_obj = {
                "sender": sender,
                "target": target,
                "message": message,
                "timestamp": time.time()
            }
            self.history.append(msg_obj)
            
            # Format message for the agent
            formatted_msg = f"MESSAGE FROM {sender}:\n{message}\n\n(Reply using `send_message` tool, or use `finish_debate` if the goal is met)"

            if target.lower() in ["broadcast", "all"]:
                for name, q in self.subscribers.items():
                    if name != sender:
                        q.put({"sender": sender, "formatted_msg": formatted_msg})
            elif target in self.subscribers:
                self.subscribers[target].put({"sender": sender, "formatted_msg": formatted_msg})

    def finish(self, summary: str):
        self.final_result = summary
        self._finished.set()

    def is_finished(self) -> bool:
        return self._finished.is_set()

    def wait_until_finished(self, timeout=None):
        self._finished.wait(timeout=timeout)
        return self.final_result
