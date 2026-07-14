import os
import time
import threading
import queue

# Active client queues for Server-Sent Events subscribers
event_queues = []
event_queues_lock = threading.Lock()

def add_client():
    """
    Registers a new SSE client connection and returns a message queue.
    """
    q = queue.Queue(maxsize=10)
    with event_queues_lock:
        event_queues.append(q)
    return q

def remove_client(q):
    """
    Unregisters an SSE client queue upon connection close.
    """
    with event_queues_lock:
        if q in event_queues:
            event_queues.remove(q)

def notify_clients(message):
    """
    Pushes a notification message to all registered client queues.
    """
    with event_queues_lock:
        for q in event_queues:
            try:
                q.put_nowait(message)
            except queue.Full:
                pass

def watch_project_loop(workspace_dir):
    """
    Scans the workspace directory recursively every 500ms.
    Fires reload notifications if any Python file is added, removed, or modified.
    """
    workspace_dir = os.path.abspath(workspace_dir)
    
    def scan_file_mtimes():
        mtimes = {}
        for root, dirs, files in os.walk(workspace_dir):
            # Ignore hidden files/folders and environment caches
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]
            for f in files:
                if f.endswith('.py'):
                    path = os.path.join(root, f)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except Exception:
                        pass
        return mtimes

    last_mtimes = scan_file_mtimes()

    while True:
        time.sleep(0.5)
        current_mtimes = scan_file_mtimes()
        
        # Check if files lists differ or modification times changed
        has_changed = False
        if set(current_mtimes.keys()) != set(last_mtimes.keys()):
            has_changed = True
        else:
            for path, mtime in current_mtimes.items():
                if last_mtimes.get(path) != mtime:
                    has_changed = True
                    break
                    
        if has_changed:
            last_mtimes = current_mtimes
            try:
                from parser import project_graph_manager
                project_graph_manager.trigger_reload()
            except Exception as e:
                print(f"Error reloading graph manager in watcher: {e}")
            notify_clients("updated")
