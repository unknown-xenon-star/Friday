import os
import sys
import time
import socket
import webbrowser
import threading

# Import module components
from watcher import watch_project_loop
from server import start_server
from legacy import legacy_visualize

def find_free_port(start_port=5000):
    """
    Locates an unused TCP port dynamically to prevent conflicts.
    """
    port = start_port
    while port < 6000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1
    return start_port

def open_browser(port):
    """
    Opens the default browser window pointing to the local dashboard.
    """
    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{port}/")

def main():
    args = sys.argv[1:]
    
    # Check for legacy CLI mode request
    if "--cli" in args:
        args.remove("--cli")
        filename = args[0] if args else "main.py"
        legacy_visualize(filename)
        return

    # Resolve workspace and target file from CLI arguments
    path = args[0] if args else "."
    
    if os.path.isdir(path):
        workspace_dir = os.path.abspath(path)
        # Default to main.py if present, or search for any python file
        if os.path.exists(os.path.join(workspace_dir, "main.py")):
            target_file = "main.py"
        else:
            py_files = [f for f in os.listdir(workspace_dir) if f.endswith(".py")]
            target_file = py_files[0] if py_files else ""
    elif os.path.isfile(path):
        workspace_dir = os.path.abspath(os.path.dirname(path))
        target_file = os.path.relpath(path, workspace_dir).replace(os.sep, '/')
    else:
        print(f"Error: Path '{path}' does not exist on disk.")
        return

    if not target_file:
        print(f"Error: No Python (.py) files found in workspace '{workspace_dir}'.")
        return

    print("Friday Call Graph Visualizer")
    print(f"Workspace: {workspace_dir}")
    print(f"Default target file: {target_file}")
    
    # Start the directory watcher in a background thread
    watcher_thread = threading.Thread(
        target=watch_project_loop, 
        args=(workspace_dir,), 
        daemon=True
    )
    watcher_thread.start()

    # Find an open port for the Flask backend
    port = find_free_port(5000)
    print(f"Web server starting on http://127.0.0.1:{port}")
    
    # Spawn browser launcher thread
    browser_thread = threading.Thread(
        target=open_browser, 
        args=(port,), 
        daemon=True
    )
    browser_thread.start()

    # Run the web server
    start_server(workspace_dir, target_file, port)

if __name__ == "__main__":
    main()