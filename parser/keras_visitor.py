import ast

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
