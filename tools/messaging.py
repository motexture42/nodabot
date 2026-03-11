from tools.base import BaseTool

class MessagingTool(BaseTool):
    """Allows the agent to send a direct message to the user."""
    
    @property
    def name(self) -> str:
        return "send_user_message"

    @property
    def description(self) -> str:
        return "Sends a direct text message to the user chat. Use this during background jobs, reminders, or when you need to ask a question as part of an autonomous mission."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message text to send to the user."
                }
            },
            "required": ["message"]
        }

    def run(self, message: str, **kwargs) -> str:
        # The agent core will handle the actual emission when it sees this tool call
        return "{\"status\": \"success\", \"action\": \"message_delivered_to_user\"}"
