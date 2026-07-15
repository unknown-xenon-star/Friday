import ast
import os
import threading
import time
import json
import ctypes
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
            base_dir = os.path.abspath(os.path.dirname(__file__))
            dll_path = os.path.join(base_dir, 'graph_core.dll')
            src_path = os.path.join(base_dir, 'graph_core.cpp')

            # If MinGW is installed, add its bin directory to PATH so dependent DLLs can be found
            # This is a heuristic – adjust the path if your MinGW location differs
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
                        capture_output=True,
                    )
                    print('[GRAPH] C++ graph core compiled successfully.')
                except Exception as compile_err:
                    print(f'[GRAPH] Compilation failed: {compile_err}')
                    # Continue to attempt loading any existing DLL

            if os.path.exists(dll_path):
                # Ensure the directory is on the DLL search path (Windows 8+ API)
                if os.name == 'nt':
                    try:
                        os.add_dll_directory(os.path.dirname(dll_path))
                    except Exception as e:
                        print(f'[GRAPH] add_dll_directory error: {e}')
                try:
                    # Use full absolute path; on Windows ctypes.CDLL will look in PATH for dependencies
                    cls._dll = ctypes.CDLL(dll_path)
                except OSError as load_err:
                    print(f'[GRAPH] Failed to load DLL: {load_err}')
                    # Print the underlying Windows error for more detail
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
                    cls._dll.get_graph_json.restype = ctypes.c_char_p
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
                return json.loads(json_bytes.decode('utf-8'))
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

KERAS_LAYERS = {
    'Dense', 'Conv1D', 'Conv2D', 'Conv3D', 'MaxPooling1D', 'MaxPooling2D', 'MaxPooling3D',
    'AveragePooling1D', 'AveragePooling2D', 'AveragePooling3D',
    'GlobalMaxPooling1D', 'GlobalMaxPooling2D', 'GlobalAveragePooling1D', 'GlobalAveragePooling2D',
    'Flatten', 'Dropout', 'BatchNormalization', 'LayerNormalization', 'Activation',
    'SimpleRNN', 'LSTM', 'GRU', 'Concatenate', 'Add', 'Multiply', 'Average', 'Maximum', 'Minimum',
    'Input', 'Reshape', 'Embedding'
}

def infer_output_shape(layer_type, configs, input_shapes):
    if layer_type == 'Input':
        shape_val = configs.get('shape') or configs.get('batch_input_shape') or configs.get('input_shape')
        if shape_val:
            if isinstance(shape_val, (list, tuple)):
                shape_list = list(shape_val)
                return [None] + shape_list
            elif isinstance(shape_val, int):
                return [None, shape_val]
        return [None, None]
        
    if not input_shapes:
        return [None, None]
    if not isinstance(input_shapes[0], (list, tuple)):
        input_shapes = [input_shapes]
    in_shape = list(input_shapes[0])
    
    if layer_type == 'Dense':
        units = configs.get('units')
        if isinstance(units, int):
            if len(in_shape) >= 2:
                return in_shape[:-1] + [units]
            return [None, units]
        return in_shape
        
    elif layer_type == 'Flatten':
        if len(in_shape) >= 2:
            prod = 1
            for dim in in_shape[1:]:
                if dim is None:
                    return [None, None]
                prod *= dim
            return [None, prod]
        return [None, None]
        
    elif layer_type in ('Conv1D', 'Conv2D', 'Conv3D'):
        filters = configs.get('filters')
        if not isinstance(filters, int):
            filters = None
        kernel_size = configs.get('kernel_size', 1)
        strides = configs.get('strides', 1)
        padding = configs.get('padding', 'valid')
        if isinstance(padding, str):
            padding = padding.lower()
            
        rank = 2
        if layer_type == 'Conv1D': rank = 1
        elif layer_type == 'Conv3D': rank = 3
        
        def to_tuple(val, n):
            if isinstance(val, (list, tuple)):
                return list(val)
            if isinstance(val, int):
                return [val] * n
            return [1] * n
            
        kernels = to_tuple(kernel_size, rank)
        stride_vals = to_tuple(strides, rank)
        
        if len(in_shape) == rank + 2:
            out_shape = [in_shape[0]]
            for i in range(rank):
                in_dim = in_shape[i + 1]
                if in_dim is None:
                    out_shape.append(None)
                    continue
                k = kernels[i]
                s = stride_vals[i]
                if padding == 'same':
                    out_dim = (in_dim + s - 1) // s
                else:
                    out_dim = (in_dim - k + s) // s
                out_shape.append(out_dim)
            out_shape.append(filters)
            return out_shape
        else:
            if filters:
                return [None] * (len(in_shape) - 1) + [filters]
            return in_shape
            
    elif layer_type in ('MaxPooling1D', 'MaxPooling2D', 'MaxPooling3D', 'AveragePooling1D', 'AveragePooling2D', 'AveragePooling3D'):
        pool_size = configs.get('pool_size', 2)
        strides = configs.get('strides', pool_size)
        padding = configs.get('padding', 'valid')
        if isinstance(padding, str):
            padding = padding.lower()
            
        rank = 2
        if '1D' in layer_type: rank = 1
        elif '3D' in layer_type: rank = 3
        
        def to_tuple(val, n):
            if isinstance(val, (list, tuple)):
                return list(val)
            if isinstance(val, int):
                return [val] * n
            return [1] * n
            
        pools = to_tuple(pool_size, rank)
        stride_vals = to_tuple(strides, rank)
        
        if len(in_shape) == rank + 2:
            out_shape = [in_shape[0]]
            for i in range(rank):
                in_dim = in_shape[i + 1]
                if in_dim is None:
                    out_shape.append(None)
                    continue
                p = pools[i]
                s = stride_vals[i]
                if padding == 'same':
                    out_dim = (in_dim + s - 1) // s
                else:
                    out_dim = (in_dim - p + s) // s
                out_shape.append(out_dim)
            out_shape.append(in_shape[-1])
            return out_shape
        return in_shape
        
    elif layer_type in ('GlobalMaxPooling1D', 'GlobalMaxPooling2D', 'GlobalAveragePooling1D', 'GlobalAveragePooling2D'):
        if len(in_shape) >= 2:
            return [in_shape[0], in_shape[-1]]
        return [None, None]
        
    elif layer_type in ('SimpleRNN', 'LSTM', 'GRU'):
        units = configs.get('units')
        return_sequences = configs.get('return_sequences', False)
        
        if isinstance(units, int):
            if return_sequences:
                if len(in_shape) >= 2:
                    return [in_shape[0], in_shape[1], units]
                return [None, None, units]
            else:
                return [None, units]
        return in_shape
        
    elif layer_type in ('Concatenate', 'Add', 'Multiply', 'Average', 'Maximum', 'Minimum'):
        if layer_type == 'Concatenate':
            axis = configs.get('axis', -1)
            if len(input_shapes) >= 1:
                ref_shape = list(input_shapes[0])
                axis_idx = axis if axis >= 0 else len(ref_shape) + axis
                concat_dim = 0
                for shape in input_shapes:
                    if len(shape) > axis_idx:
                        dim = shape[axis_idx]
                        if dim is None:
                            concat_dim = None
                            break
                        concat_dim += dim
                    else:
                        concat_dim = None
                        break
                if concat_dim is not None:
                    ref_shape[axis_idx] = concat_dim
                    return ref_shape
                return ref_shape
        return in_shape
        
    return in_shape

class SubclassedCallTracer(ast.NodeVisitor):
    def __init__(self, namespace_prefix, class_layers, input_node_ids, input_shapes, visitor):
        self.namespace_prefix = namespace_prefix
        self.class_layers = class_layers
        self.visitor = visitor
        self.variables = {}
        self.input_node_ids = input_node_ids
        self.input_shapes = input_shapes
        
    def visit_FunctionDef(self, node):
        if node.name in ('call', 'forward'):
            args = [arg.arg for arg in node.args.args]
            if len(args) >= 2:
                input_arg_name = args[1]
                if self.input_node_ids:
                    self.variables[input_arg_name] = {
                        'node_id': self.input_node_ids[0],
                        'shape': self.input_shapes[0] if self.input_shapes else [None, None]
                    }
            self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets) != 1:
            self.generic_visit(node)
            return
            
        target = node.targets[0]
        val_node = node.value
        
        target_name = self.visitor.get_name_from_node(target)
        if not target_name:
            self.generic_visit(node)
            return
            
        if isinstance(val_node, ast.Call):
            func_name = self.visitor.get_name_from_node(val_node.func)
            if func_name and func_name.startswith('self.'):
                attr_name = func_name.split('.')[-1]
                if attr_name in self.class_layers:
                    layer_info = self.class_layers[attr_name]
                    layer_type = layer_info['layer_type']
                    configs = layer_info['configs']
                    
                    node_id = f"{self.namespace_prefix}/{attr_name}"
                    
                    input_nodes = []
                    input_shapes = []
                    if val_node.args:
                        outer_arg = val_node.args[0]
                        name = self.visitor.get_name_from_node(outer_arg)
                        if name in self.variables:
                            info = self.variables[name]
                            input_nodes.append(info['node_id'])
                            input_shapes.append(info['shape'])
                                
                    out_shape = infer_output_shape(layer_type, configs, input_shapes)
                    
                    self.visitor.nodes.append({
                        'id': node_id,
                        'label': f"{attr_name} ({layer_type})",
                        'type': 'layer',
                        'layer_type': layer_type,
                        'output_shape': str(out_shape),
                        'parameters': layer_info['params_str'],
                        'filepath': self.visitor.filepath,
                        'lineno': val_node.lineno,
                        'namespace': self.namespace_prefix
                    })
                    
                    for idx, in_id in enumerate(input_nodes):
                        in_shape = input_shapes[idx] if idx < len(input_shapes) else [None, None]
                        self.visitor.edges.append({
                            'from': in_id,
                            'to': node_id,
                            'tensor_shape': str(in_shape),
                            'type': 'dataflow'
                        })
                        
                    self.variables[target_name] = {
                        'node_id': node_id,
                        'shape': out_shape
                    }
                    return
        
        self.generic_visit(node)

    def visit_Return(self, node):
        if isinstance(node.value, ast.Call):
            func_name = self.visitor.get_name_from_node(node.value.func)
            if func_name and func_name.startswith('self.'):
                attr_name = func_name.split('.')[-1]
                if attr_name in self.class_layers:
                    layer_info = self.class_layers[attr_name]
                    layer_type = layer_info['layer_type']
                    configs = layer_info['configs']
                    
                    node_id = f"{self.namespace_prefix}/{attr_name}"
                    
                    input_nodes = []
                    input_shapes = []
                    if node.value.args:
                        outer_arg = node.value.args[0]
                        name = self.visitor.get_name_from_node(outer_arg)
                        if name in self.variables:
                            info = self.variables[name]
                            input_nodes.append(info['node_id'])
                            input_shapes.append(info['shape'])
                                
                    out_shape = infer_output_shape(layer_type, configs, input_shapes)
                    
                    self.visitor.nodes.append({
                        'id': node_id,
                        'label': f"{attr_name} ({layer_type})",
                        'type': 'layer',
                        'layer_type': layer_type,
                        'output_shape': str(out_shape),
                        'parameters': layer_info['params_str'],
                        'filepath': self.visitor.filepath,
                        'lineno': node.value.lineno,
                        'namespace': self.namespace_prefix
                    })
                    
                    for idx, in_id in enumerate(input_nodes):
                        in_shape = input_shapes[idx] if idx < len(input_shapes) else [None, None]
                        self.visitor.edges.append({
                            'from': in_id,
                            'to': node_id,
                            'tensor_shape': str(in_shape),
                            'type': 'dataflow'
                        })
                        
                    self.variables['__return__'] = {
                        'node_id': node_id,
                        'shape': out_shape
                    }
        self.generic_visit(node)

class KerasModelVisitor(ast.NodeVisitor):
    def __init__(self, module_name, filepath):
        self.module_name = module_name
        self.filepath = filepath
        self.nodes = []
        self.edges = []
        self.import_map = {}
        self.layer_counters = {}
        self.variables = {}
        
        self.current_class = None
        self.class_layers = {}
        self.subclassed_classes = {}
        
    def get_next_id(self, layer_type):
        l_type = layer_type.lower()
        self.layer_counters[l_type] = self.layer_counters.get(l_type, 0) + 1
        return f"{l_type}_{self.layer_counters[l_type]}"
        
    def resolve_import(self, name):
        if not name:
            return ""
        parts = name.split('.')
        first = parts[0]
        if first in self.import_map:
            resolved = self.import_map[first]
            if len(parts) > 1:
                return f"{resolved}.{'.'.join(parts[1:])}"
            return resolved
        return name

    def get_name_from_node(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self.get_name_from_node(node.value)
            if val:
                return f"{val}.{node.attr}"
            return node.attr
        return None

    def get_layer_type_from_call(self, node):
        if not isinstance(node, ast.Call):
            return None
        name = self.get_name_from_node(node.func)
        if not name:
            return None
        resolved = self.resolve_import(name)
        for layer in KERAS_LAYERS:
            if resolved == layer or resolved.endswith('.' + layer) or name == layer or name.endswith('.' + layer):
                return layer
        return None

    def get_arg_value_str(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return f"'{node.value}'"
            return str(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Tuple):
            elts = [self.get_arg_value_str(elt) for elt in node.elts]
            return f"({', '.join(elts)})"
        elif isinstance(node, ast.List):
            elts = [self.get_arg_value_str(elt) for elt in node.elts]
            return f"[{', '.join(elts)}]"
        elif isinstance(node, ast.Call):
            return f"{self.get_name_from_node(node.func)}(...)"
        return "..."

    def evaluate_ast_node(self, node):
        try:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Tuple):
                return tuple(self.evaluate_ast_node(e) for e in node.elts)
            elif isinstance(node, ast.List):
                return [self.evaluate_ast_node(e) for e in node.elts]
            elif isinstance(node, ast.Dict):
                keys = [self.evaluate_ast_node(k) for k in node.keys]
                vals = [self.evaluate_ast_node(v) for v in node.values]
                return dict(zip(keys, vals))
        except Exception:
            pass
        return None

    def parse_layer_args(self, node, layer_type):
        configs = {}
        params_list = []
        
        for i, arg in enumerate(node.args):
            val_str = self.get_arg_value_str(arg)
            val = self.evaluate_ast_node(arg)
            param_name = f"arg_{i}"
            if layer_type == 'Dense':
                if i == 0:
                    param_name = 'units'
                    configs['units'] = val
                elif i == 1:
                    param_name = 'activation'
                    configs['activation'] = val
            elif layer_type in ('Conv1D', 'Conv2D', 'Conv3D'):
                if i == 0:
                    param_name = 'filters'
                    configs['filters'] = val
                elif i == 1:
                    param_name = 'kernel_size'
                    configs['kernel_size'] = val
                elif i == 2:
                    param_name = 'strides'
                    configs['strides'] = val
                elif i == 3:
                    param_name = 'padding'
                    configs['padding'] = val
            elif layer_type == 'Dropout':
                if i == 0:
                    param_name = 'rate'
                    configs['rate'] = val
            elif layer_type in ('MaxPooling2D', 'AveragePooling2D'):
                if i == 0:
                    param_name = 'pool_size'
                    configs['pool_size'] = val
                elif i == 1:
                    param_name = 'strides'
                    configs['strides'] = val
                elif i == 2:
                    param_name = 'padding'
                    configs['padding'] = val
            elif layer_type == 'Input':
                if i == 0:
                    param_name = 'shape'
                    configs['shape'] = val
            params_list.append(f"{param_name}={val_str}")
            
        for kw in node.keywords:
            val_str = self.get_arg_value_str(kw.value)
            val = self.evaluate_ast_node(kw.value)
            configs[kw.arg] = val
            params_list.append(f"{kw.arg}={val_str}")
            
        return ", ".join(params_list), configs

    def visit_Import(self, node):
        for alias in node.names:
            self.import_map[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.import_map[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        is_subclassed = False
        for base in node.bases:
            base_name = self.get_name_from_node(base)
            if base_name:
                res_base = self.resolve_import(base_name)
                if any(x in res_base or x in base_name for x in ('Model', 'Layer', 'tf.keras.Model', 'keras.Model')):
                    is_subclassed = True
                    break
        
        if is_subclassed:
            self.current_class = node.name
            self.class_layers = {}
            self.generic_visit(node)
            self.subclassed_classes[node.name] = {
                'layers': self.class_layers,
                'filepath': self.filepath,
                'lineno': node.lineno,
                'node': node
            }
            self.current_class = None
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets) != 1:
            self.generic_visit(node)
            return
            
        target = node.targets[0]
        val_node = node.value
        
        if self.current_class and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
            attr_name = target.attr
            if isinstance(val_node, ast.Call):
                layer_type = self.get_layer_type_from_call(val_node)
                if layer_type:
                    params_str, configs = self.parse_layer_args(val_node, layer_type)
                    self.class_layers[attr_name] = {
                        'layer_type': layer_type,
                        'params_str': params_str,
                        'configs': configs,
                        'lineno': val_node.lineno
                    }
            self.generic_visit(node)
            return

        target_name = self.get_name_from_node(target)
        if not target_name:
            self.generic_visit(node)
            return

        if isinstance(val_node, ast.Call):
            func_name = self.get_name_from_node(val_node.func)
            if func_name:
                res_func = self.resolve_import(func_name)
                if 'Sequential' in res_func or 'Sequential' in func_name:
                    node_id = self.get_next_id('Sequential')
                    self.nodes.append({
                        'id': node_id,
                        'label': 'Sequential',
                        'type': 'layer',
                        'layer_type': 'Sequential',
                        'output_shape': '[None, None]',
                        'parameters': '',
                        'filepath': self.filepath,
                        'lineno': val_node.lineno,
                        'namespace': self.module_name
                    })
                    
                    self.variables[target_name] = {
                        'type': 'Sequential',
                        'node_id': node_id,
                        'layers': [],
                        'shape': [None, None]
                    }
                    
                    if val_node.args and isinstance(val_node.args[0], ast.List):
                        for item in val_node.args[0].elts:
                            if isinstance(item, ast.Call):
                                self.add_to_sequential(target_name, item)
                    self.generic_visit(node)
                    return

            layer_type = self.get_layer_type_from_call(val_node)
            if layer_type == 'Input':
                node_id = self.get_next_id('Input')
                params_str, configs = self.parse_layer_args(val_node, 'Input')
                out_shape = infer_output_shape('Input', configs, [])
                self.nodes.append({
                    'id': node_id,
                    'label': 'Input',
                    'type': 'input',
                    'layer_type': 'Input',
                    'output_shape': str(out_shape),
                    'parameters': params_str,
                    'filepath': self.filepath,
                    'lineno': val_node.lineno,
                    'namespace': self.module_name
                })
                self.variables[target_name] = {
                    'node_id': node_id,
                    'shape': out_shape
                }
                self.generic_visit(node)
                return

            if isinstance(val_node.func, ast.Call):
                creator_call = val_node.func
                layer_type = self.get_layer_type_from_call(creator_call)
                if layer_type:
                    params_str, configs = self.parse_layer_args(creator_call, layer_type)
                    node_id = self.get_next_id(layer_type)
                    
                    input_nodes = []
                    input_shapes = []
                    if val_node.args:
                        outer_arg = val_node.args[0]
                        if isinstance(outer_arg, (ast.List, ast.Tuple)):
                            for elt in outer_arg.elts:
                                name = self.get_name_from_node(elt)
                                if name in self.variables:
                                    info = self.variables[name]
                                    input_nodes.append(info['node_id'])
                                    input_shapes.append(info['shape'])
                        else:
                            name = self.get_name_from_node(outer_arg)
                            if name in self.variables:
                                info = self.variables[name]
                                input_nodes.append(info['node_id'])
                                input_shapes.append(info['shape'])
                                
                    out_shape = infer_output_shape(layer_type, configs, input_shapes)
                    
                    self.nodes.append({
                        'id': node_id,
                        'label': layer_type,
                        'type': 'layer',
                        'layer_type': layer_type,
                        'output_shape': str(out_shape),
                        'parameters': params_str,
                        'filepath': self.filepath,
                        'lineno': val_node.lineno,
                        'namespace': self.module_name
                    })
                    
                    for idx, in_id in enumerate(input_nodes):
                        in_shape = input_shapes[idx] if idx < len(input_shapes) else [None, None]
                        self.edges.append({
                            'from': in_id,
                            'to': node_id,
                            'tensor_shape': str(in_shape),
                            'type': 'dataflow'
                        })
                        
                    self.variables[target_name] = {
                        'node_id': node_id,
                        'shape': out_shape
                    }
                    self.generic_visit(node)
                    return
                    
            func_name = self.get_name_from_node(val_node.func)
            if func_name:
                res_func = self.resolve_import(func_name)
                matched_class = None
                for c_name in self.subclassed_classes:
                    if res_func == c_name or func_name == c_name:
                        matched_class = c_name
                        break
                if matched_class:
                    self.variables[target_name] = {
                        'type': 'Subclassed',
                        'class_name': matched_class,
                        'node_id': target_name,
                        'filepath': self.filepath,
                        'lineno': val_node.lineno
                    }
                    self.generic_visit(node)
                    return

            if func_name and (func_name.startswith('tf.') or func_name.startswith('tensorflow.')):
                op_name = func_name.split('.')[-1]
                node_id = self.get_next_id(op_name)
                
                input_nodes = []
                input_shapes = []
                for arg in val_node.args:
                    name = self.get_name_from_node(arg)
                    if name in self.variables:
                        info = self.variables[name]
                        input_nodes.append(info['node_id'])
                        input_shapes.append(info['shape'])
                        
                out_shape = input_shapes[0] if input_shapes else [None, None]
                self.nodes.append({
                    'id': node_id,
                    'label': op_name,
                    'type': 'operation',
                    'layer_type': op_name,
                    'output_shape': str(out_shape),
                    'parameters': '',
                    'filepath': self.filepath,
                    'lineno': val_node.lineno,
                    'namespace': self.module_name
                })
                
                for idx, in_id in enumerate(input_nodes):
                    in_shape = input_shapes[idx] if idx < len(input_shapes) else [None, None]
                    self.edges.append({
                        'from': in_id,
                        'to': node_id,
                        'tensor_shape': str(in_shape),
                        'type': 'dataflow'
                    })
                    
                self.variables[target_name] = {
                    'node_id': node_id,
                    'shape': out_shape
                }
                self.generic_visit(node)
                return

        if isinstance(val_node, ast.Call):
            caller_name = self.get_name_from_node(val_node.func)
            if caller_name and caller_name in self.variables:
                caller_info = self.variables[caller_name]
                if caller_info.get('type') == 'Subclassed':
                    class_name = caller_info['class_name']
                    input_nodes = []
                    input_shapes = []
                    if val_node.args:
                        outer_arg = val_node.args[0]
                        name = self.get_name_from_node(outer_arg)
                        if name in self.variables:
                            info = self.variables[name]
                            input_nodes.append(info['node_id'])
                            input_shapes.append(info['shape'])
                            
                    self.trace_subclassed_call(caller_name, class_name, input_nodes, input_shapes, target_name)
                    self.generic_visit(node)
                    return
        
        self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr == 'add':
                var_name = self.get_name_from_node(func.value)
                if var_name in self.variables and self.variables[var_name].get('type') == 'Sequential':
                    if node.value.args:
                        layer_call = node.value.args[0]
                        if isinstance(layer_call, ast.Call):
                            self.add_to_sequential(var_name, layer_call)
        self.generic_visit(node)

    def add_to_sequential(self, seq_var_name, layer_call):
        layer_type = self.get_layer_type_from_call(layer_call)
        if not layer_type:
            return
            
        params_str, configs = self.parse_layer_args(layer_call, layer_type)
        node_id = self.get_next_id(layer_type)
        
        seq_info = self.variables[seq_var_name]
        prev_layers = seq_info['layers']
        prev_shape = seq_info['shape']
        
        if not prev_layers and 'input_shape' in configs:
            in_shape = infer_output_shape('Input', {'shape': configs['input_shape']}, [])
        else:
            in_shape = prev_shape
            
        out_shape = infer_output_shape(layer_type, configs, [in_shape])
        
        self.nodes.append({
            'id': node_id,
            'label': layer_type,
            'type': 'layer',
            'layer_type': layer_type,
            'output_shape': str(out_shape),
            'parameters': params_str,
            'filepath': self.filepath,
            'lineno': layer_call.lineno,
            'namespace': f"{self.module_name}.{seq_var_name}"
        })
        
        if prev_layers:
            prev_id = prev_layers[-1]
            self.edges.append({
                'from': prev_id,
                'to': node_id,
                'tensor_shape': str(in_shape),
                'type': 'dataflow'
            })
        elif 'input_shape' in configs:
            input_id = self.get_next_id('Input')
            input_shape_val = configs['input_shape']
            in_node_shape = infer_output_shape('Input', {'shape': input_shape_val}, [])
            self.nodes.append({
                'id': input_id,
                'label': 'Input',
                'type': 'input',
                'layer_type': 'Input',
                'output_shape': str(in_node_shape),
                'parameters': f"shape={input_shape_val}",
                'filepath': self.filepath,
                'lineno': layer_call.lineno,
                'namespace': f"{self.module_name}.{seq_var_name}"
            })
            self.edges.append({
                'from': input_id,
                'to': node_id,
                'tensor_shape': str(in_node_shape),
                'type': 'dataflow'
            })
            
        seq_info['layers'].append(node_id)
        seq_info['shape'] = out_shape

    def trace_subclassed_call(self, instance_name, class_name, input_nodes, input_shapes, target_name):
        class_def = self.subclassed_classes.get(class_name)
        if not class_def:
            return
            
        tracer = SubclassedCallTracer(instance_name, class_def['layers'], input_nodes, input_shapes, self)
        tracer.visit(class_def['node'])
        
        if '__return__' in tracer.variables:
            ret_info = tracer.variables['__return__']
            self.variables[target_name] = {
                'node_id': ret_info['node_id'],
                'shape': ret_info['shape']
            }
        else:
            for child in ast.walk(class_def['node']):
                if isinstance(child, ast.FunctionDef) and child.name in ('call', 'forward'):
                    for stmt in child.body:
                        if isinstance(stmt, ast.Return):
                            ret_name = self.get_name_from_node(stmt.value)
                            if ret_name in tracer.variables:
                                ret_info = tracer.variables[ret_name]
                                self.variables[target_name] = {
                                    'node_id': ret_info['node_id'],
                                    'shape': ret_info['shape']
                                }

class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self, module_name, filepath):
        self.module_name = module_name
        self.filepath = filepath
        self.scope_stack = []
        self.nodes_meta = {}  # qualified_name -> meta
        self.edges = {}       # (caller, callee, edge_type) -> count
        self.import_map = {}  # local_name -> qualified_name

    def calculate_complexity(self, node):
        """
        Recursively calculates the cyclomatic complexity index of a given AST block
        by counting decision/branching points.
        """
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp, ast.Match)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def get_current_scope_name(self):
        """
        Reconstructs the full dot-separated scope path of the current position in the AST.
        """
        if not self.scope_stack:
            return None
        return '.'.join([item[1] for item in self.scope_stack])

    def get_current_function(self):
        """
        Returns the full dot-separated name of the nearest enclosing function scope,
        or None if not inside a function.
        """
        names = []
        is_in_function = False
        for scope_type, scope_name in self.scope_stack:
            names.append(scope_name)
            if scope_type == 'function':
                is_in_function = True
        if is_in_function:
            return '.'.join(names)
        return None

    def get_enclosing_class(self):
        """
        Returns the name of the nearest enclosing class.
        """
        for scope_type, scope_name in reversed(self.scope_stack):
            if scope_type == 'class':
                return scope_name
        return None

    def get_decorator_name(self, node):
        """
        Extracts the name of a decorator (supports both @decorator and @decorator(args) formats).
        """
        if isinstance(node, ast.Call):
            return self.get_name_from_attribute_or_name(node.func)
        return self.get_name_from_attribute_or_name(node)

    def get_name_from_attribute_or_name(self, node):
        """
        Recursively extracts the name of a variable, function, or chain of attributes (e.g. obj.method).
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self.get_name_from_attribute_or_name(node.value)
            if val:
                return f"{val}.{node.attr}"
            return node.attr
        return None

    def add_edge(self, caller, callee, edge_type="call"):
        """
        Adds a graph edge and tracks edge multiplicity count.
        """
        key = (caller, callee, edge_type)
        self.edges[key] = self.edges.get(key, 0) + 1

    def visit_Import(self, node):
        # Capture import mapping: import module as alias
        for alias in node.names:
            local_name = alias.asname or alias.name
            self.import_map[local_name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # Capture import mapping: from module import func as alias
        if node.module:
            for alias in node.names:
                local_name = alias.asname or alias.name
                self.import_map[local_name] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.scope_stack.append(('class', node.name))
        full_class_name = self.get_current_scope_name()
        qual_class_name = f"{self.module_name}.{full_class_name}"
        
        # Collect class decorators
        decorators = [self.get_decorator_name(d) for d in node.decorator_list]
        decorators = [d for d in decorators if d is not None]
        
        # Calculate size & complexity metrics
        loc = (node.end_lineno - node.lineno + 1) if hasattr(node, 'end_lineno') else None
        complexity = self.calculate_complexity(node)
        
        self.nodes_meta[qual_class_name] = {
            "is_defined": True,
            "is_class": True,
            "lineno": node.lineno,
            "decorators": decorators,
            "complexity": complexity,
            "loc": loc,
            "filepath": self.filepath
        }
        
        # Link class to its decorators
        for dec_name in decorators:
            dec_resolved = self.resolve_import_name(dec_name)
            self.add_edge(qual_class_name, dec_resolved, edge_type="decorator")
            
        # Add structural containment edge if nested
        if len(self.scope_stack) >= 2:
            parent_scope = '.'.join([item[1] for item in self.scope_stack[:-1]])
            qual_parent = f"{self.module_name}.{parent_scope}"
            self.add_edge(qual_parent, qual_class_name, edge_type="containment")
                
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node):
        self.scope_stack.append(('function', node.name))
        full_func_name = self.get_current_scope_name()
        qual_func_name = f"{self.module_name}.{full_func_name}"
        
        # Collect function decorators
        decorators = [self.get_decorator_name(d) for d in node.decorator_list]
        decorators = [d for d in decorators if d is not None]
        
        # Calculate size & complexity metrics
        loc = (node.end_lineno - node.lineno + 1) if hasattr(node, 'end_lineno') else None
        complexity = self.calculate_complexity(node)
        
        self.nodes_meta[qual_func_name] = {
            "is_defined": True,
            "is_class": False,
            "lineno": node.lineno,
            "decorators": decorators,
            "complexity": complexity,
            "loc": loc,
            "filepath": self.filepath
        }
        
        # Link function to its decorators
        for dec_name in decorators:
            dec_resolved = self.resolve_import_name(dec_name)
            self.add_edge(qual_func_name, dec_resolved, edge_type="decorator")

        # Add structural containment edge if nested
        if len(self.scope_stack) >= 2:
            parent_scope = '.'.join([item[1] for item in self.scope_stack[:-1]])
            qual_parent = f"{self.module_name}.{parent_scope}"
            self.add_edge(qual_parent, qual_func_name, edge_type="containment")
                
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        caller = self.get_current_function()
        if not caller and not self.scope_stack:
            # Top-level call at the module scope
            caller = f"{self.module_name}.<module>"
            if caller not in self.nodes_meta:
                self.nodes_meta[caller] = {
                    "is_defined": True,
                    "is_class": False,
                    "lineno": 1,
                    "decorators": [],
                    "complexity": None,
                    "loc": None,
                    "filepath": self.filepath
                }
        elif caller:
            caller = f"{self.module_name}.{caller}"
            
        if caller:
            called = self.get_name_from_attribute_or_name(node.func)
            if called:
                # Heuristic: Map calls to self.method() inside class context
                # back to the class definition scope: ClassName.method()
                if called.startswith("self."):
                    current_class = self.get_enclosing_class()
                    if current_class:
                        called = called.replace("self.", f"{current_class}.", 1)
                        
                # We save raw call and resolve it in post-processing!
                self.add_edge(caller, called, edge_type="call")
                
        self.generic_visit(node)

    def resolve_import_name(self, name):
        if not name:
            return name
        segments = name.split('.')
        first_seg = segments[0]
        if first_seg in self.import_map:
            mapped = self.import_map[first_seg]
            if len(segments) > 1:
                return f"{mapped}.{'.'.join(segments[1:])}"
            return mapped
        return name

class ProjectGraphManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.workspace_dir = None
        self.target_file = None
        self.overlays = {}
        self.visitors = {}
        self.keras_visitors = {}
        self.parsed_files = set()
        self.unparsed_files = []
        self.visible_node_ids = set()
        self.pending_nodes = []
        self.bg_thread = None
        self.bg_running = False
        self.ack_event = threading.Event()

    def init_workspace(self, workspace_dir, target_file):
        with self.lock:
            # Stop any existing background thread
            self.bg_running = False
            self.ack_event.set()
            
            self.workspace_dir = os.path.abspath(workspace_dir)
            self.target_file = target_file
            self.overlays = {}
            self.visitors = {}
            self.keras_visitors = {}
            self.parsed_files = set()
            self.visible_node_ids = set()
            self.pending_nodes = []
            
            # 1. Discover all Python files
            py_files = []
            for root, dirs, files in os.walk(self.workspace_dir):
                # Skip hidden directories, caches, and virtual environments
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', 'env', 'node_modules')]
                for f in files:
                    if f.endswith('.py'):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, self.workspace_dir).replace(os.sep, '/')
                        py_files.append(rel_path)
            
            # Standardize target_file
            target_rel = self.target_file.replace(os.sep, '/')
            
            # Ensure target_file is parsed first
            first_file = target_rel if target_rel in py_files else (py_files[0] if py_files else None)
            if first_file:
                if first_file in py_files:
                    py_files.remove(first_file)
                self.target_file = first_file
                
                # Parse target file synchronously
                visitor, keras_visitor = self.parse_file_to_visitors(first_file)
                if visitor:
                    self.visitors[first_file] = visitor
                    self.keras_visitors[first_file] = keras_visitor
                    self.parsed_files.add(first_file)
                    
                    # Extract its defined nodes
                    nodes = list(visitor.nodes_meta.keys())
                    if nodes:
                        # Start with the first node visible
                        self.visible_node_ids.add(nodes[0])
                        # The rest are pending
                        self.pending_nodes = nodes[1:]
            
            # The remaining files will be parsed in the background
            self.unparsed_files = py_files
            
            # Start background thread
            self.bg_running = True
            self.bg_thread = threading.Thread(target=self.run_background_parse, daemon=True)
            self.bg_thread.start()

    def parse_file_to_visitors(self, rel_path, code=None):
        abs_path = os.path.join(self.workspace_dir, rel_path)
        
        # Calculate module name
        base, ext = os.path.splitext(rel_path)
        if os.path.basename(base) == "__init__":
            module_name = os.path.dirname(base).replace('/', '.')
        else:
            module_name = base.replace('/', '.')
        if not module_name:
            module_name = "root"
            
        try:
            if code is None:
                if rel_path in self.overlays:
                    code = self.overlays[rel_path]
                else:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        code = f.read()
                        
            tree = ast.parse(code)
            visitor = FunctionCallVisitor(module_name, rel_path)
            visitor.visit(tree)
            
            keras_visitor = KerasModelVisitor(module_name, rel_path)
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
                        'filepath': rel_path,
                        'lineno': class_def['lineno'],
                        'namespace': class_name
                    })
                    keras_visitor.trace_subclassed_call(class_name, class_name, [input_id], [[None, None]], '__dummy__')
            
            return visitor, keras_visitor
        except Exception as e:
            print(f"Error parsing file {rel_path} incrementally: {e}")
            return None, None

    def run_background_parse(self):
        while self.bg_running:
            node_to_reveal = None
            
            with self.lock:
                if self.pending_nodes:
                    node_to_reveal = self.pending_nodes.pop(0)
                elif self.unparsed_files:
                    next_file = self.unparsed_files.pop(0)
                    visitor, keras_visitor = self.parse_file_to_visitors(next_file)
                    if visitor:
                        self.visitors[next_file] = visitor
                        self.keras_visitors[next_file] = keras_visitor
                        self.parsed_files.add(next_file)
                        
                        nodes = list(visitor.nodes_meta.keys())
                        if nodes:
                            node_to_reveal = nodes[0]
                            self.pending_nodes.extend(nodes[1:])
                else:
                    self.bg_running = False
                    break
            
            if node_to_reveal:
                self.ack_event.clear()
                
                with self.lock:
                    self.visible_node_ids.add(node_to_reveal)
                
                # Get current graph
                graph = self.get_current_graph()
                
                # Send the update to all clients
                try:
                    from watcher import notify_clients
                    payload = {
                        "type": "file_parsed",
                        "nodes": graph["nodes"],
                        "edges": graph["edges"],
                        "model_graph": graph["model_graph"],
                        "pending_updates": len(self.pending_nodes) + len(self.unparsed_files)
                    }
                    notify_clients(json.dumps(payload))
                except Exception as e:
                    print(f"Error notifying clients: {e}")
                    self.ack_event.set()
                
                # Wait for client acknowledgment before proceeding
                self.ack_event.wait(timeout=5.0)
                    
            time.sleep(0.01)

    def get_current_graph(self):
        with self.lock:
            visitors_list = list(self.visitors.values())
            keras_list = list(self.keras_visitors.values())
            
            project_modules = set(v.module_name for v in visitors_list)
            defined_names = set()
            for v in visitors_list:
                defined_names.update(v.nodes_meta.keys())
                
            model_nodes = []
            model_edges = []
            for kv in keras_list:
                model_nodes.extend(kv.nodes)
                model_edges.extend(kv.edges)
                
            global_nodes_meta = {}
            global_edges = {}
            
            for v in visitors_list:
                global_nodes_meta.update(v.nodes_meta)
                
            for v in visitors_list:
                module_name = v.module_name
                for (u, val, edge_type), count in v.edges.items():
                    if edge_type in ('decorator', 'containment'):
                        key = (u, val, edge_type)
                        global_edges[key] = global_edges.get(key, 0) + count
                    elif edge_type == 'call':
                        resolved = v.resolve_import_name(val)
                        if resolved in defined_names:
                            called_id = resolved
                        else:
                            local_qual = f"{module_name}.{val}"
                            first_seg = val.split('.')[0]
                            local_qual_first = f"{module_name}.{first_seg}"
                            
                            if local_qual in defined_names:
                                called_id = local_qual
                            elif local_qual_first in defined_names:
                                called_id = local_qual
                            else:
                                if first_seg in project_modules:
                                    called_id = val
                                else:
                                    called_id = resolved
                                    
                        key = (u, called_id, 'call')
                        global_edges[key] = global_edges.get(key, 0) + count
                        
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
            
            # Now filter the graph based on visible node ids!
            actual_visible = set(self.visible_node_ids)
            
            # Add any callee of a visible node to actual_visible
            for (u, val, edge_type) in global_edges.keys():
                if u in self.visible_node_ids:
                    actual_visible.add(val)
                    
            cpp_graph = CppGraph()
            called_targets = set(k[1] for k in global_edges.keys() if k[2] == 'call' and k[0] in actual_visible)
            
            for name, meta in global_nodes_meta.items():
                if name not in actual_visible:
                    continue
                    
                is_unused = False
                if meta["is_defined"] and not meta["is_class"] and not name.endswith(".<module>"):
                    if name not in called_targets:
                        is_unused = True
                        
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
                
            for (u, val, edge_type), count in global_edges.items():
                if u in actual_visible and val in actual_visible:
                    cpp_graph.add_edge(u, val, count, edge_type)
                    
            # Filter Keras model nodes based on visible namespace or prefix
            model_visible_node_ids = set()
            for node in model_nodes:
                ns = node.get('namespace', '')
                if ns in actual_visible or any(ns.startswith(v + '.') or ns.startswith(v + '/') for v in actual_visible):
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
                    model_visible_node_ids.add(node['id'])
                    
            for edge in model_edges:
                if edge['from'] in model_visible_node_ids and edge['to'] in model_visible_node_ids:
                    cpp_graph.add_model_edge(edge["from"], edge["to"], edge.get("tensor_shape") or "")
                    
            return cpp_graph.get_dict()

    def update_overlay(self, filepath, code):
        filepath = filepath.replace('\\', '/')
        with self.lock:
            self.overlays[filepath] = code
            
            # Parse it sync
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
