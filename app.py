import os
import threading
import queue
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO

from core.agent import Agent
from config import Config
from utils.tools import get_tools
from utils.watcher_manager import WatcherManager
from utils.app_helpers import emit_event, heartbeat_loop
from interfaces.telegram_bot import TelegramInterface

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DEDICATED WORKER THREAD ---
# This ensures Playwright and other thread-sensitive tools stay alive across turns
task_queue = queue.Queue()

def enqueue_task(msg):
    if msg == '/reset': 
        # For resets, we can clear the queue to prevent old tasks from running
        while not task_queue.empty():
            try: task_queue.get_nowait()
            except: pass
        task_queue.put(msg)
    else:
        # Enqueue the task for the worker thread
        task_queue.put(msg)

telegram_bot = TelegramInterface(enqueue_callback=enqueue_task)
telegram_bot.start()

# Initialize global components
def wrapped_emit(event_type, data):
    emit_event(socketio, event_type, data)
    telegram_bot.emit(event_type, data)

main_agent = Agent(
    tools=get_tools(emit_cb=wrapped_emit), 
    session_id="main", 
    emit_cb=wrapped_emit, 
    name="Main"
)

watcher_manager = WatcherManager(main_agent, emit_cb=wrapped_emit)

def agent_worker_loop():
    while True:
        msg = task_queue.get()
        if msg is None: break # Poison pill to shutdown
        try:
            main_agent.run(msg)
            # Sync watchers if the last action might have affected them
            if any("manage_watchers" in str(m) for m in main_agent.history[-2:]):
                watcher_manager.sync()
        except Exception as e:
            print(f"Worker Error: {e}")
        finally:
            task_queue.task_done()

# Start the immortal worker thread
worker_thread = threading.Thread(target=agent_worker_loop, daemon=True)
worker_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory(os.path.join(os.getcwd(), Config.SCREENSHOT_DIR), filename)

@socketio.on('connect')
def handle_connect():
    # Clean history for the UI
    cleaned_history = []
    for msg in main_agent.history:
        m = msg.copy()
        if m.get("role") == "assistant" and m.get("content"):
            m["content"] = main_agent._clean_content(m["content"])
        cleaned_history.append(m)
        
    socketio.emit('session_history', {'history': cleaned_history})
    socketio.emit('mission_update', {
        "mission": main_agent.current_mission, 
        "next_step": main_agent.next_planned_step
    })
    socketio.emit('metrics_update', {
        "tokens": main_agent.session_tokens,
        "actions": main_agent.total_actions,
        "errors": main_agent.total_errors
    })
    
    scheduler = main_agent.tool_map.get("manage_jobs")
    if scheduler:
        socketio.emit('jobs_update', {"jobs": scheduler.jobs})
    
    watchers = main_agent.tool_map.get("manage_watchers")
    if watchers: 
        socketio.emit('watchers_update', {"watchers": watchers.active_watchers})
        watcher_manager.sync()

@socketio.on('remove_job')
def handle_remove_job(data):
    jid = data.get('job_id')
    scheduler = main_agent.tool_map.get("manage_jobs")
    if jid and scheduler:
        res = scheduler.run(action="remove", job_id=jid)
        wrapped_emit('system_msg', {'message': res})
        wrapped_emit('jobs_update', {'jobs': scheduler.jobs})

@socketio.on('remove_watcher')
def handle_remove_watcher(data):
    wid = data.get('watcher_id')
    watchers = main_agent.tool_map.get("manage_watchers")
    if wid and watchers:
        res = watchers.run(action="stop", watcher_id=wid)
        wrapped_emit('system_msg', {'message': res})
        wrapped_emit('watchers_update', {'watchers': watchers.active_watchers})
        watcher_manager.sync()

@socketio.on('user_message')
def handle_message(data):
    msg = data.get('message', '')
    if msg:
        enqueue_task(msg)

if __name__ == '__main__':
    print(f"Starting NodaBot UI on http://127.0.0.1:{Config.PORT}")
    socketio.start_background_task(heartbeat_loop, socketio, main_agent, wrapped_emit)
    socketio.run(app, debug=Config.DEBUG, port=Config.PORT, use_reloader=False)
