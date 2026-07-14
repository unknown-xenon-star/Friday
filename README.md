# Friday Call Graph Visualizer

A project-wide, interactive call graph visualizer for Python workspaces. It recursively scans directories, parses Python ASTs, resolves cross-module imports statically, and renders an interactive, physics-driven network of classes, functions, annotations, and call flows.

Features a split-pane web UI with an embedded code editor (**Monaco Editor**) on the left and an interactive network canvas (**vis-network**) on the right.

---

## Key Features

*   **Workspace-Wide Multi-File Discovery**: Scans folders recursively, prefixes definitions using module-level namespace paths, and connects call references across separate files.
*   **Module Dependency Graph View**: Aggregates function calls up to the file level. Displays directories as rectangular box nodes with accumulated lines of code (LOC), complexity sums, class counts, and function counts.
*   **Complexity Heatmap View**: Fills user defined functions with dynamic color scales based on complexity (Blue $\le 3$ for Simple, Amber $4$-$7$ for Moderate, Red $> 7$ for Complex) to quickly identify logical hotspots.
*   **Static Import Resolution**: Resolves `import` and `from ... import` statements to accurately link function and class method invocations across module boundaries.
*   **Dynamic Monaco File Swapping**: Double-clicking a node defined in a different file dynamically swaps Monaco Editor's content, displays the file path in the header badge, and scrolls to the defined line.
*   **Live Overlay Compilation**: Editing inside the editor debounces (300ms) and compiles the active file as an *overlay* inside the global project call graph, updating linkages instantly as you type.
*   **Workspace Hot-Reloading**: Watcher recursively monitors all files in the project folder, reloading the browser automatically when any Python file is saved.
*   **Upstream/Downstream Focus Mode**: Selecting any node isolates its upstream callers and downstream callees, highlighting the full execution path while fading out unrelated nodes to 15% opacity.
*   **Metrics Overlay**: Hovering nodes displays static analysis metrics such as **Lines of Code (LOC)** and **Cyclomatic Complexity** (decision branch density), complete with warning alerts (e.g. `⚠️ High complexity` or `Long function`).
*   **Search Box**: Floating input to quickly find, focus, and highlight pathways for matching functions or classes.
*   **Classes and Structural Containment**: Isolates classes as green boxes and visualizes method containment (`defines` relationships) to automatically group class methods near their parent class.
*   **Decorator Mapping**: Tracks decorators (simple or parameterized) and represents wrapping dependencies as gold dashed lines.
*   **External Call Declutter Filter**: A toolbar toggle button (`Libs`) to instantly hide or show external calls and standard builtins (e.g. `print()`), keeping focus on your local application structure.
*   **Force Decay Damping**: A custom physics slider to adjust graph simulation friction dynamically.
*   **Legacy Mode**: Still supports drawing static matplotlib-based window call graphs.

---

## Project Structure

*   `main.py`: Entrypoint and orchestrator (args parser, port allocation, browser launcher, server initiator).
*   `parser.py`: Scope-aware AST parser (tracks namespaces, computes metrics, detects unused functions project-wide).
*   `watcher.py`: Workspace directory watcher background thread.
*   `server.py`: Flask web API endpoints & Server-Sent Events stream.
*   `legacy.py`: Legacy Matplotlib call graph visualization CLI.
*   `index.html`: Web dashboard asset (styled dashboard UI with Monaco Editor and vis-network).
*   `documentation.md`: Detailed developer guide (APIs, internals, mechanics).

---

## Installation & Requirements

Ensure you have `Flask` and `networkx` installed in your environment:
```bash
pip install Flask networkx matplotlib
```

---

## Quick Start

### 1. Run Workspace Web Dashboard (Default)
To analyze the current directory (`.`):
```bash
python main.py
```
To analyze a custom project folder:
```bash
python main.py path/to/another_project_directory
```
To analyze a single target file:
```bash
python main.py path/to/your_script.py
```
*This starts the Flask server on `http://127.0.0.1:5000` (or next free port) and opens your web browser automatically.*

### 2. Run Legacy CLI Graph
To render a static call graph window using `matplotlib`:
```bash
python main.py --cli
```
Or for a custom script:
```bash
python main.py --cli path/to/your_script.py
```

---

## Documentation

For a detailed breakdown of routing, static analysis algorithms, and frontend configurations, check:
*   **[documentation.md](file:///d:/uv/13-07-2026/Friday/documentation.md)**: Server APIs and parser internals.
*   **[walkthrough.md](file:///C:/Users/Xenon/.gemini/antigravity-ide/brain/0cfa61c0-53f4-418c-bfe6-2adbf44f080d/walkthrough.md)**: Visual legends, options, and architecture layouts.
