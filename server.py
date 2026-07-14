import os
import logging
from flask import Flask, send_from_directory, jsonify, request, Response, current_app

# Import utility functions from other modules
from parser import parse_code_to_graph, parse_project_to_graph, project_graph_manager
from watcher import add_client, remove_client

app = Flask(__name__, static_folder='static', static_url_path='')

@app.route('/')
def serve_index():
    """
    Serves the main frontend dashboard page.
    """
    return send_from_directory('static', 'index.html')

@app.route('/api/config')
def get_config():
    """
    Returns configuration properties, including target file, workspace dir, and default preferences.
    """
    import json
    target = current_app.config.get('TARGET_FILE', 'main.py')
    workspace = current_app.config.get('WORKSPACE_DIR', '.')
    
    defaults = {
        "libs": "on",
        "physics": "on",
        "layout": "spring",
        "view": "function",
        "color_mode": "standard"
    }
    
    config_file_path = os.path.join(workspace, 'friday.json')
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if isinstance(user_config, dict) and "defaults" in user_config:
                    defaults.update(user_config["defaults"])
        except Exception as e:
            print(f"Error loading configuration file: {e}")
            
    return jsonify({
        "target_file": target,
        "target_file_basename": os.path.basename(target),
        "workspace_dir": os.path.abspath(workspace),
        "defaults": defaults
    })

@app.route('/api/file-content')
def get_file_content():
    """
    Reads and returns the raw string content of a requested file path relative to workspace.
    """
    workspace = current_app.config.get('WORKSPACE_DIR', '.')
    target = request.args.get('file', current_app.config.get('TARGET_FILE', 'main.py'))
    
    # Safe path resolution to prevent directory traversal
    target_path = os.path.abspath(os.path.join(workspace, target))
    if not target_path.startswith(os.path.abspath(workspace)):
        return jsonify({"error": "Access Denied"}), 403
        
    if not os.path.exists(target_path):
        return jsonify({"error": f"File '{target}' not found on disk"}), 404
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/graph')
def get_graph():
    """
    Generates and returns the project-wide call graph of the workspace.
    """
    workspace = current_app.config.get('WORKSPACE_DIR', '.')
    target = current_app.config.get('TARGET_FILE', 'main.py')
    
    if not project_graph_manager.workspace_dir:
        project_graph_manager.init_workspace(workspace, target)
        
    return jsonify(project_graph_manager.get_current_graph())

@app.route('/api/parse', methods=['POST'])
def parse_code():
    """
    Parses live Python code text, overriding a target file in the project
    to enable live multi-file graph recompiles as the developer types.
    """
    data = request.json or {}
    code = data.get('code', '')
    filepath = data.get('filepath', '')
    
    workspace = current_app.config.get('WORKSPACE_DIR', '.')
    target = current_app.config.get('TARGET_FILE', 'main.py')
    
    if not project_graph_manager.workspace_dir:
        project_graph_manager.init_workspace(workspace, target)
        
    if filepath:
        return jsonify(project_graph_manager.update_overlay(filepath, code))
        
    # Fallback to single file parsing
    return jsonify(parse_code_to_graph(code))

@app.route('/api/events')
def get_events():
    """
    Sets up Server-Sent Events (SSE) so the client browser receives file edit events.
    """
    q = add_client()
    
    def event_stream():
        try:
            while True:
                # Wait for notifications published by the watcher thread
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            pass
        finally:
            remove_client(q)
            
    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/api/ack', methods=['POST'])
def acknowledge_update():
    """
    Receives acknowledgment from the client that it has processed/rendered the latest update.
    """
    project_graph_manager.acknowledge_update()
    return jsonify({"status": "acknowledged"})

def start_server(workspace_dir, target_file, port):
    """
    Configures and starts the Flask web server.
    """
    app.config['WORKSPACE_DIR'] = workspace_dir
    app.config['TARGET_FILE'] = target_file
    
    # Eagerly initialize the workspace call graph manager
    project_graph_manager.init_workspace(workspace_dir, target_file)
    
    # Minimize logs to keep output clean and focus on error reporting
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
