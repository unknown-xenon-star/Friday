import ast
import networkx as nx
import matplotlib.pyplot as plt

def legacy_visualize(filename):
    """
    Renders a static call graph window of a Python file using networkx and matplotlib.
    This corresponds to the original behavior of main.py.
    """
    print(f"Generating legacy static graph for {filename}...")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return

    class LegacyVisitor(ast.NodeVisitor):
        def __init__(self):
            self.graph = nx.DiGraph()
            self.current_function = None

        def visit_FunctionDef(self, node):
            previous = self.current_function
            self.current_function = node.name
            self.graph.add_node(node.name)
            self.generic_visit(node)
            self.current_function = previous

        def visit_Call(self, node):
            if self.current_function:
                if isinstance(node.func, ast.Name):
                    called = node.func.id
                    self.graph.add_edge(self.current_function, called)
                elif isinstance(node.func, ast.Attribute):
                    called = node.func.attr
                    self.graph.add_edge(self.current_function, called)
            self.generic_visit(node)

    visitor = LegacyVisitor()
    visitor.visit(tree)

    if not visitor.graph.nodes:
        print("Warning: No function definitions or calls found. The graph is empty.")

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(visitor.graph, seed=42)
    
    nx.draw_networkx_nodes(
        visitor.graph,
        pos,
        node_size=2500
    )
    
    nx.draw_networkx_edges(
        visitor.graph,
        pos,
        arrows=True,
        arrowsize=20
    )
    
    nx.draw_networkx_labels(
        visitor.graph,
        pos,
        font_size=10,
        font_weight="bold"
    )
    
    plt.title(f"Python Function Call Graph ({filename})")
    plt.axis("off")
    plt.tight_layout()
    plt.show()
