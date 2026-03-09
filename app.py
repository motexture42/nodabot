import os
import threading
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO

from core.agent import Agent
from config import Config
from utils.tools import get_tools
from utils.watcher_manager import WatcherManager
from utils.app_helpers import emit_event, heartbeat_loop

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize global components
def wrapped_emit(event_type, data):
    emit_event(socketio, event_type, data)

main_agent = Agent(
    tools=get_tools(emit_cb=wrapped_emit), 
    session_id="main", 
    emit_cb=wrapped_emit, 
    name="Main"
)

watcher_manager = WatcherManager(main_agent, emit_cb=wrapped_emit)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory(os.path.join(os.getcwd(), Config.SCREENSHOT_DIR), filename)

@socketio.on('connect')
def handle_connect():
    socketio.emit('session_history', {'history': main_agent.history})
    socketio.emit('mission_update', {
        "mission": main_agent.current_mission, 
        "next_step": main_agent.next_planned_step
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
    if msg == '/reset': 
        main_agent.run(msg)
        watcher_manager.sync()
    else:
        def run_task():
            main_agent.run(msg)
            # Sync watchers if the last action might have affected them
            # Check last 2 messages for tool calls to manage_watchers
            if any("manage_watchers" in str(m) for m in main_agent.history[-2:]):
                watcher_manager.sync()
        threading.Thread(target=run_task).start()

if __name__ == '__main__':
    print(f"Starting NodaBot UI on http://127.0.0.1:{Config.PORT}")
    socketio.start_background_task(heartbeat_loop, socketio, main_agent, wrapped_emit)
    socketio.run(app, debug=Config.DEBUG, port=Config.PORT, use_reloader=False)
