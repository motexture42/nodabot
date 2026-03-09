import os
from flask_socketio import SocketIO

def emit_event(socketio: SocketIO, event_type: str, data: dict):
    socketio.emit(event_type, data)

def heartbeat_loop(socketio: SocketIO, agent, emit_cb):
    while True:
        socketio.sleep(30)
        emit_cb("heartbeat", {"timestamp": os.getpid()})
        try:
            agent.heartbeat()
        except Exception as e:
            print(f"Heartbeat Error: {e}")
