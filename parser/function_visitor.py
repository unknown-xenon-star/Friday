import ast

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
            # Heuristic: Map top-level call to <module> scope
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
                # Heuristic: Map self.method() calls back to ClassName.method()
                if called.startswith("self."):
                    current_class = self.get_enclosing_class()
                    if current_class:
                        called = called.replace("self.", f"{current_class}.", 1)
                        
                # We save raw call and resolve it in post-processing
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
