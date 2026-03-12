import threading
import uuid

class ApprovalManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ApprovalManager, cls).__new__(cls)
            cls._instance.pending = {}
        return cls._instance

    def request_approval(self, command: str, emit_cb) -> bool:
        req_id = str(uuid.uuid4())
        event = threading.Event()
        self.pending[req_id] = {"event": event, "approved": False}
        
        if emit_cb:
            emit_cb('approval_request', {"id": req_id, "command": command})
            
        # Block until user responds, or timeout after 120 seconds
        event.wait(timeout=120.0)
        
        if req_id in self.pending:
            approved = self.pending[req_id]["approved"]
            del self.pending[req_id]
            return approved
        return False

    def resolve(self, req_id: str, approved: bool):
        if req_id in self.pending:
            self.pending[req_id]["approved"] = approved
            self.pending[req_id]["event"].set()

approval_manager = ApprovalManager()
