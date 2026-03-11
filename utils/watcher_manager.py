import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class WatcherHandler(FileSystemEventHandler):
    def __init__(self, agent, emit_cb):
        self.agent = agent
        self.emit_cb = emit_cb

    def on_created(self, event): self._trigger(event, "created")
    def on_modified(self, event): self._trigger(event, "modified")
    def on_moved(self, event): self._trigger(event, "moved")

    def _trigger(self, event, action_type):
        if event.is_directory: return
        path = os.path.abspath(event.dest_path if action_type == "moved" else event.src_path)
        watcher_tool = self.agent.tool_map.get("manage_watchers")
        if not watcher_tool: return
        
        for wid, wdata in watcher_tool.active_watchers.items():
            watch_target = os.path.abspath(wdata['path'])
            # Trigger if the path is exactly the file OR if the path is inside the watched directory
            if path == watch_target or (os.path.isdir(watch_target) and path.startswith(watch_target)):
                print(f"[👀] Watcher {wid} triggered by {action_type}: {path}")
                if self.emit_cb:
                    self.emit_cb('system_msg', {'message': f'👀 Watcher triggered: {os.path.basename(path)}'})
                task_prompt = f"COMMAND: A file event '{action_type}' occurred at '{path}'. Your task: '{wdata['task']}'. Execute now and report back to the user."
                threading.Thread(target=lambda: self.agent.run(task_prompt, is_internal=True)).start()
                break

class WatcherManager:
    def __init__(self, agent, emit_cb=None):
        self.agent = agent
        self.emit_cb = emit_cb
        self.observer = Observer()
        self.watch_lock = threading.Lock()
        self.observer.start()

    def sync(self):
        """Sync the watchdog observer with the tool's active_watchers."""
        with self.watch_lock:
            watcher_tool = self.agent.tool_map.get("manage_watchers")
            if not watcher_tool: return
            self.observer.unschedule_all()
            handler = WatcherHandler(self.agent, self.emit_cb)
            
            # Track directories we are already watching to avoid redundant observers
            watched_dirs = set()
            for wid, wdata in watcher_tool.active_watchers.items():
                path = wdata['path']
                if not os.path.exists(path): continue
                
                # If it's a file, watch the parent directory
                dir_to_watch = path if os.path.isdir(path) else os.path.dirname(path)
                if dir_to_watch not in watched_dirs:
                    try:
                        self.observer.schedule(handler, dir_to_watch, recursive=False)
                        watched_dirs.add(dir_to_watch)
                    except Exception as e: print(f"Watch Error {dir_to_watch}: {e}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
