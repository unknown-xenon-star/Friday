import os
import ast
import threading
from .cpp_interface import CppGraph
from .keras_visitor import KerasModelVisitor
from .function_visitor import FunctionCallVisitor

class ProjectGraphManager:
    def __init__(self):
        self.workspace_dir = None
        self.target_file = None
        self.visitors = {}
        self.keras_visitors = {}
        self.parsed_files = set()
        self.visible_node_ids = set()
        self.overlays = {}
        
        self.ack_event = threading.Event()
        self.ack_event.set()
        
    def init_workspace(self, workspace_dir, target_file):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.target_file = target_file
        self.visitors.clear()
        self.keras_visitors.clear()
        self.parsed_files.clear()
        self.visible_node_ids.clear()
        self.overlays.clear()
        
        # Initial parse
        self.get_current_graph()
        
    def get_current_graph(self):
        if not self.workspace_dir:
            return {"nodes": [], "edges": [], "model_graph": {"nodes": [], "edges": []}}
            
        # Parse the workspace using current overlays
        graph = parse_project_to_graph(self.workspace_dir, overlays=self.overlays)
        if "error" in graph:
            return graph
            
        # If active file not parsed (e.g. not in .py files), make sure we parse it
        if self.target_file and self.target_file not in self.parsed_files:
            # Try to force parse it
            target_path = os.path.join(self.workspace_dir, self.target_file)
            if os.path.exists(target_path):
                try:
                    rel_path = self.target_file.replace('\\', '/')
                    with open(target_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    tree = ast.parse(code)
                    module_name = os.path.splitext(rel_path)[0].replace('/', '.')
                    visitor = FunctionCallVisitor(module_name, rel_path)
                    visitor.visit(tree)
                    self.visitors[rel_path] = visitor
                    
                    keras_visitor = KerasModelVisitor(module_name, rel_path)
                    keras_visitor.visit(tree)
                    self.keras_visitors[rel_path] = keras_visitor
                    
                    self.parsed_files.add(rel_path)
                except Exception as e:
                    print(f"Failed to force parse target file: {e}")
                    
        return graph
        
    def update_overlay(self, filepath, code):
        filepath = filepath.replace('\\\\', '/')
        if code is None:
            if filepath in self.overlays:
                del self.overlays[filepath]
        else:
            self.overlays[filepath] = code
            
            # Re-parse this file immediately
            base, ext = os.path.splitext(filepath)
            if os.path.basename(base) == "__init__":
                module_name = os.path.dirname(base).replace('/', '.')
            else:
                module_name = base.replace('/', '.')
            if not module_name:
                module_name = "root"
                
            try:
                tree = ast.parse(code)
                visitor = FunctionCallVisitor(module_name, filepath)
                visitor.visit(tree)
                
                keras_visitor = KerasModelVisitor(module_name, filepath)
                keras_visitor.visit(tree)
                
                # Trace subclassed Keras models if any
                called_subclassed = set()
                for var_info in keras_visitor.variables.values():
                    if isinstance(var_info, dict) and var_info.get('type') == 'Subclassed':
                        called_subclassed.add(var_info['class_name'])
                for class_name, class_def in keras_visitor.subclassed_classes.items():
                    if class_name not in called_subclassed:
                        input_id = f"{class_name}_input"
                        keras_visitor.nodes.append({
                            'id': input_id,
                            'label': 'Input',
                            'type': 'input',
                            'layer_type': 'Input',
                            'output_shape': '[None, None]',
                            'parameters': '',
                            'filepath': filepath,
                            'lineno': class_def['lineno'],
                            'namespace': class_name
                        })
                        keras_visitor.trace_subclassed_call(class_name, class_name, [input_id], [[None, None]], '__dummy__')
                
                # Store
                self.visitors[filepath] = visitor
                self.keras_visitors[filepath] = keras_visitor
                self.parsed_files.add(filepath)
                
                # Automatically add all nodes from this visitor to visible_node_ids
                for node_id in visitor.nodes_meta.keys():
                    self.visible_node_ids.add(node_id)
            except Exception as e:
                print(f"Error parsing overlay file {filepath}: {e}")
                
        return self.get_current_graph()

    def trigger_reload(self):
        if self.workspace_dir and self.target_file:
            self.init_workspace(self.workspace_dir, self.target_file)

    def acknowledge_update(self):
        self.ack_event.set()

project_graph_manager = ProjectGraphManager()

def parse_project_to_graph(workspace_dir, overlays=None):
    """
    Scans a workspace directory recursively, parses all Python files,
    resolves imports statically, and constructs a project-wide call graph.
    Allows passing editor code updates as overlays to dynamically compile unsaved editor changes.
    """
    workspace_dir = os.path.abspath(workspace_dir)
    overlays = overlays or {}
    py_files = []
    
    # 1. Discover all Python files
    for root, dirs, files in os.walk(workspace_dir):
        # Skip hidden directories, caches, and virtual environments
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
                
    visitors = []
    defined_names = set()
    project_modules = set()
    model_nodes = []
    model_edges = []
    
    # 2. Parse each discovered file
    for filepath in py_files:
        rel_path = os.path.relpath(filepath, workspace_dir).replace(os.sep, '/')
        
        # Convert file path relative to workspace into module name
        base, ext = os.path.splitext(rel_path)
        if os.path.basename(base) == "__init__":
            module_name = os.path.dirname(base).replace('/', '.')
        else:
            module_name = base.replace('/', '.')
            
        if not module_name:
            module_name = "root"
            
        project_modules.add(module_name)
        
        try:
            # Check if this file has a live content overlay in the editor
            if rel_path in overlays:
                content = overlays[rel_path]
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            
            tree = ast.parse(content)
            visitor = FunctionCallVisitor(module_name, rel_path)
            visitor.visit(tree)
            visitors.append(visitor)
            
            # Record local definition names
            for name in visitor.nodes_meta.keys():
                defined_names.add(name)
                
            # --- Parse TensorFlow/Keras Model Graph ---
            keras_visitor = KerasModelVisitor(module_name, rel_path)
            keras_visitor.visit(tree)
            
            # Subclassed fallback (if a subclassed model class was defined but not instantiated in the file)
            called_subclassed = set()
            for var_info in keras_visitor.variables.values():
                if isinstance(var_info, dict) and var_info.get('type') == 'Subclassed':
                    called_subclassed.add(var_info['class_name'])
            for class_name, class_def in keras_visitor.subclassed_classes.items():
                if class_name not in called_subclassed:
                    input_id = f"{class_name}_input"
                    keras_visitor.nodes.append({
                        'id': input_id,
                        'label': 'Input',
                        'type': 'input',
                        'layer_type': 'Input',
                        'output_shape': '[None, None]',
                        'parameters': '',
                        'filepath': rel_path,
                        'lineno': class_def['lineno'],
                        'namespace': class_name
                    })
                    keras_visitor.trace_subclassed_call(class_name, class_name, [input_id], [[None, None]], '__dummy__')
            
            model_nodes.extend(keras_visitor.nodes)
            model_edges.extend(keras_visitor.edges)
                
        except SyntaxError as se:
            # Return syntax error directly if parsing fails
            return {"error": f"Syntax Error in {rel_path} (line {se.lineno}, col {se.offset}): {se.msg}"}
        except Exception as e:
            return {"error": f"Failed to parse project file '{rel_path}': {str(e)}"}
            
    # 3. Post-process call edges
    global_nodes_meta = {}
    global_edges = {}  # (from, to, type) -> count
    
    # Collect all defined nodes from all files
    for visitor in visitors:
        global_nodes_meta.update(visitor.nodes_meta)
        
    for visitor in visitors:
        module_name = visitor.module_name
        
        for (u, v, edge_type), count in visitor.edges.items():
            if edge_type in ('decorator', 'containment'):
                # Decorators and containment links are already fully resolved
                key = (u, v, edge_type)
                global_edges[key] = global_edges.get(key, 0) + count
            elif edge_type == 'call':
                # Map raw destination string v:
                # A: Try resolving using import aliases mapping
                resolved = visitor.resolve_import_name(v)
                
                if resolved in defined_names:
                    called_id = resolved
                else:
                    # B: Check if it's calling a sibling function inside the same module
                    local_qual = f"{module_name}.{v}"
                    first_seg = v.split('.')[0]
                    local_qual_first = f"{module_name}.{first_seg}"
                    
                    if local_qual in defined_names:
                        called_id = local_qual
                    elif local_qual_first in defined_names:
                        called_id = local_qual
                    else:
                        # C: Check if it is a call to another module directly
                        if first_seg in project_modules:
                            called_id = v
                        else:
                            # It is an external/library call (e.g. print)
                            called_id = resolved
                            
                # Register connection
                key = (u, called_id, 'call')
                global_edges[key] = global_edges.get(key, 0) + count
                
                # Register external calls in global metadata
                if called_id not in global_nodes_meta:
                    global_nodes_meta[called_id] = {
                        "is_defined": False,
                        "is_class": False,
                        "lineno": None,
                        "decorators": [],
                        "complexity": None,
                        "loc": None,
                        "filepath": None
                    }
                    
    # 4. Determine dead code (unused functions) project-wide
    called_targets = set()
    for (u, v, edge_type), count in global_edges.items():
        if edge_type == 'call':
            called_targets.add(v)
            
    cpp_graph = CppGraph()

    for name, meta in global_nodes_meta.items():
        is_unused = False
        if meta["is_defined"] and not meta["is_class"] and not name.endswith(".<module>"):
            if name not in called_targets:
                is_unused = True
                
        # Generate base name label relative to module scope
        label = name
        module_prefix = None
        for mod in project_modules:
            if name.startswith(mod + '.'):
                label = name[len(mod)+1:]
                module_prefix = mod
                break
                
        cpp_graph.add_node(
            name,
            label,
            meta["is_defined"],
            meta["is_class"],
            meta["lineno"],
            meta["filepath"],
            meta["loc"],
            meta["complexity"],
            is_unused,
            module_prefix,
            meta["decorators"]
        )
        
    for (u, v, edge_type), count in global_edges.items():
        cpp_graph.add_edge(u, v, count, edge_type)

    for node in model_nodes:
        cpp_graph.add_model_node(
            node["id"],
            node.get("label") or "",
            node.get("type") or node.get("layer_type") or "",
            node.get("output_shape") or "",
            node.get("parameters") or "",
            node.get("filepath") or "",
            node.get("lineno"),
            node.get("namespace") or ""
        )

    for edge in model_edges:
        cpp_graph.add_model_edge(edge["from"], edge["to"], edge.get("tensor_shape") or "")
        
    return cpp_graph.get_dict()

def parse_code_to_graph(code_str):
    """
    Maintains compatibility for single file parsing.
    """
    try:
        return parse_project_to_graph(".", overlays={"main.py": code_str})
    except Exception as e:
        return {"error": f"Parsing Error: {str(e)}"}

def parse_file_to_graph(filepath):
    """
    Maintains compatibility for single file parsing.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        return parse_code_to_graph(code)
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}
