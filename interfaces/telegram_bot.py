import telebot
import threading
import json
from config import Config

class TelegramInterface:
    def __init__(self, enqueue_callback=None):
        self.enqueue_callback = enqueue_callback
        self.bot = None
        self.last_reply = None
        
        # We fetch from Config or os.environ if available
        self.chat_id = getattr(Config, 'TELEGRAM_CHAT_ID', None)
        token = getattr(Config, 'TELEGRAM_BOT_TOKEN', None)
        
        if token and self.chat_id:
            try:
                self.bot = telebot.TeleBot(token)
                self._setup_handlers()
            except Exception as e:
                print(f"Error initializing Telegram bot: {e}")
                self.bot = None
                
    def _setup_handlers(self):
        @self.bot.message_handler(func=lambda message: str(message.chat.id) == str(self.chat_id))
        def handle_message(message):
            if self.enqueue_callback and message.text:
                self.last_reply = None  # Reset deduplication for new user message
                self.enqueue_callback(message.text)
                
    def start(self):
        if self.bot:
            print("Starting Telegram bot...")
            # We catch exceptions to prevent the bot from crashing on network timeouts
            # Using default timeouts instead of custom ones to prevent urllib3 ReadTimeoutError
            threading.Thread(target=self.bot.infinity_polling, kwargs={"logger_level": 30}, daemon=True).start()
            
    def _send_long_message(self, text):
        max_len = 4000
        for i in range(0, len(text), max_len):
            try:
                self.bot.send_message(self.chat_id, text[i:i+max_len])
            except Exception as e:
                print(f"Failed to send chunk: {e}")

    def emit(self, event_type, data):
        if not self.bot or not self.chat_id:
            return
            
        try:
            if event_type == "agent_reply":
                content = data.get("content", "")
                if content:
                    if content != self.last_reply:
                        self._send_long_message(f"🤖 Agent:\n{content}")
                        self.last_reply = content
                    
            elif event_type == "system_msg":
                message = data.get("message", "")
                if message:
                    self._send_long_message(f"⚙️ System: {message}")
                    
            elif event_type == "tool_start":
                tool = data.get("tool", "")
                args = data.get("args", {})
                args_str = json.dumps(args, indent=2)
                if len(args_str) > 1000:
                    args_str = args_str[:1000] + "\n... [truncated]"
                self._send_long_message(f"🛠 Using tool: {tool}\nArgs: {args_str}")
                
            elif event_type == "tool_end":
                tool = data.get("tool", "")
                result = str(data.get("result", ""))
                if len(result) > 1000:
                    result = result[:1000] + "\n... [truncated]"
                self._send_long_message(f"✅ Tool Finished: {tool}\nResult:\n{result}")
                
            elif event_type == "agent_status":
                status = data.get("status", "")
                if status == "thinking":
                    self.bot.send_chat_action(self.chat_id, 'typing')
                    
        except Exception as e:
            print(f"Telegram emit error: {e}")
