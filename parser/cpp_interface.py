import os
import ctypes
import json
import subprocess

class CppGraph:
    _dll = None
    _compilation_tried = False

    @classmethod
    def load_dll(cls):
        # Return already loaded DLL
        if cls._dll is not None:
            return cls._dll
        # Avoid repeated attempts after a failure
        if cls._compilation_tried:
            return None
        cls._compilation_tried = True
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            dll_path = os.path.join(base_dir, 'graph_core.dll')
            src_path = os.path.join(base_dir, 'graph_core.cpp')

            # If MinGW is installed, add its bin directory to PATH so dependent DLLs can be found
            import shutil
            gxx_path = shutil.which('g++')
            gxx_dir = None
            if gxx_path:
                gxx_dir = os.path.dirname(os.path.abspath(gxx_path))
                if os.path.isdir(gxx_dir):
                    os.environ['PATH'] = gxx_dir + os.pathsep + os.environ.get('PATH', '')
            else:
                mingw_bin = os.path.expanduser('C:/Program Files/mingw-w64/bin')
                if os.path.isdir(mingw_bin):
                    os.environ['PATH'] = mingw_bin + os.pathsep + os.environ.get('PATH', '')

            # Compile the DLL on the fly if source is present and DLL missing
            if not os.path.exists(dll_path) and os.path.exists(src_path):
                print('[GRAPH] Compiling C++ graph core...')
                try:
                    subprocess.run(
                        ['g++', '-O3', '-shared', '-o', dll_path, src_path],
                        check=True,
                        capture_output=True
                    )
                    print('[GRAPH] C++ graph core compiled successfully.')
                except Exception as compile_err:
                    print(f'[GRAPH] Compilation failed: {compile_err}')

            if os.path.exists(dll_path):
                # Ensure the directory is on the DLL search path (Windows 8+ API)
                if os.name == 'nt':
                    try:
                        os.add_dll_directory(os.path.dirname(dll_path))
                    except Exception as e:
                        print(f'[GRAPH] add_dll_directory error: {e}')
                    if gxx_dir and os.path.isdir(gxx_dir):
                        try:
                            os.add_dll_directory(gxx_dir)
                        except Exception as e:
                            print(f'[GRAPH] add_dll_directory g++ error: {e}')
                try:
                    # Use full absolute path; on Windows ctypes.CDLL will look in PATH for dependencies
                    cls._dll = ctypes.CDLL(dll_path)
                except OSError as load_err:
                    print(f'[GRAPH] Failed to load DLL: {load_err}')
                    try:
                        import ctypes.wintypes as wt
                        err = ctypes.WinError()
                        print(f'[GRAPH] WinError: {err}')
                    except Exception:
                        pass
                    cls._dll = None
                else:
                    # Setup DLL argument & return types
                    cls._dll.create_graph.argtypes = []
                    cls._dll.create_graph.restype = ctypes.c_void_p
                    cls._dll.free_graph.argtypes = [ctypes.c_void_p]
                    cls._dll.free_graph.restype = None
                    cls._dll.add_node.argtypes = [
                        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_bool,
                        ctypes.c_bool, ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                        ctypes.c_int, ctypes.c_bool, ctypes.c_char_p, ctypes.c_char_p,
                    ]
                    cls._dll.add_node.restype = None
                    cls._dll.add_edge.argtypes = [
                        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
                    ]
                    cls._dll.add_edge.restype = None
                    cls._dll.add_model_node.argtypes = [
                        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
                    ]
                    cls._dll.add_model_node.restype = None
                    cls._dll.add_model_edge.argtypes = [
                        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p
                    ]
                    cls._dll.add_model_edge.restype = None
                    cls._dll.get_graph_json.argtypes = [ctypes.c_void_p]
                    cls._dll.get_graph_json.restype = ctypes.c_void_p
                    # Free function for C-allocated JSON string (prevents memory leak)
                    cls._dll.free_json_string.argtypes = [ctypes.c_void_p]
                    cls._dll.free_json_string.restype = None
            else:
                print('[GRAPH] DLL not found after compilation attempt.')
                cls._dll = None
        except Exception as e:
            print(f'[GRAPH] Unexpected error loading C++ library: {e}')
            cls._dll = None
        return cls._dll

    def __init__(self):
        self.dll = self.load_dll()
        if self.dll:
            try:
                self.handle = self.dll.create_graph()
            except Exception as e:
                print(f"Failed to create native C++ graph instance: {e}. Using Python fallback.")
                self.handle = None
        else:
            self.handle = None
            
        if self.handle is None:
            self.fallback_nodes = {}
            self.fallback_edges = []
            self.fallback_model_nodes = []
            self.fallback_model_edges = []

    def __del__(self):
        if hasattr(self, 'handle') and self.handle and self.dll:
            try:
                self.dll.free_graph(self.handle)
            except:
                pass

    def add_node(self, node_id, label, is_defined, is_class, lineno, filepath, loc, complexity, is_unused, module_prefix, decorators):
        if self.handle:
            dec_csv = ",".join(decorators) if decorators else ""
            self.dll.add_node(
                self.handle,
                node_id.encode('utf-8'),
                (label or "").encode('utf-8'),
                is_defined,
                is_class,
                lineno if lineno is not None else -1,
                filepath.encode('utf-8') if filepath else b"",
                loc if loc is not None else -1,
                complexity if complexity is not None else -1,
                is_unused,
                module_prefix.encode('utf-8') if module_prefix else b"",
                dec_csv.encode('utf-8')
            )
        else:
            self.fallback_nodes[node_id] = {
                "id": node_id,
                "label": label,
                "is_defined": is_defined,
                "is_class": is_class,
                "lineno": lineno,
                "filepath": filepath,
                "loc": loc,
                "complexity": complexity,
                "is_unused": is_unused,
                "module_prefix": module_prefix,
                "decorators": decorators
            }

    def add_edge(self, from_id, to_id, value, edge_type):
        if self.handle:
            self.dll.add_edge(
                self.handle, 
                from_id.encode('utf-8'), 
                to_id.encode('utf-8'), 
                value, 
                edge_type.encode('utf-8') if edge_type else b""
            )
        else:
            self.fallback_edges.append({
                "from": from_id,
                "to": to_id,
                "value": value,
                "type": edge_type
            })

    def add_model_node(self, node_id, label, layer_type, shape, params, filepath, lineno, namespace):
        if self.handle:
            self.dll.add_model_node(
                self.handle,
                node_id.encode('utf-8'),
                (label or "").encode('utf-8'),
                (layer_type or "").encode('utf-8'),
                (shape or "").encode('utf-8'),
                (params or "").encode('utf-8'),
                (filepath or "").encode('utf-8'),
                lineno if lineno is not None else -1,
                (namespace or "").encode('utf-8')
            )
        else:
            self.fallback_model_nodes.append({
                "id": node_id,
                "label": label,
                "type": layer_type,
                "layer_type": layer_type,
                "output_shape": shape,
                "parameters": params,
                "filepath": filepath,
                "lineno": lineno,
                "namespace": namespace
            })

    def add_model_edge(self, from_id, to_id, tensor_shape):
        if self.handle:
            self.dll.add_model_edge(
                self.handle, 
                from_id.encode('utf-8'), 
                to_id.encode('utf-8'), 
                (tensor_shape or "").encode('utf-8')
            )
        else:
            self.fallback_model_edges.append({
                "from": from_id,
                "to": to_id,
                "tensor_shape": tensor_shape
            })

    def get_dict(self):
        if self.handle:
            try:
                json_bytes = self.dll.get_graph_json(self.handle)
                if json_bytes is None:
                    return {"nodes": [], "edges": [], "model_graph": {"nodes": [], "edges": []}}
                json_str = ctypes.string_at(json_bytes).decode('utf-8')
                self.dll.free_json_string(json_bytes)
                return json.loads(json_str)
            except Exception as e:
                print(f"Failed to read JSON from C++ graph core: {e}. Using empty dict.")
                return {"nodes": [], "edges": [], "model_graph": {"nodes": [], "edges": []}}
        else:
            return {
                "nodes": list(self.fallback_nodes.values()),
                "edges": self.fallback_edges,
                "model_graph": {
                    "nodes": self.fallback_model_nodes,
                    "edges": self.fallback_model_edges
                }
            }
