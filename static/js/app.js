import { state } from './state.js';
import { showToast, showBanner, showUpdateToast, logMessage } from './ui.js';
import { syncWithDisk, parseCodeOnServer, switchActiveFile } from './editor.js';
import { initializeGraph, updateGraphView, updateGraphViewDebounced, startStabilization, resetHighlight, highlightNodeConnections } from './graph.js';

// Monaco Editor Loader Setup
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' } });
require(['vs/editor/editor.main'], function () {
    state.editor = monaco.editor.create(document.getElementById('editor-container'), {
        value: '',
        language: 'python',
        theme: 'vs-dark',
        automaticLayout: true,
        fontSize: 14,
        minimap: { enabled: false },
        lineHeight: 22,
        fontFamily: 'JetBrains Mono',
        padding: { top: 10 }
    });

    // Set up event listeners for code change
    let debounceTimer;
    state.editor.onDidChangeModelContent(function () {
        if (state.isCodeChangingProgrammatically) return;

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            const code = state.editor.getValue();
            parseCodeOnServer(code);
        }, 300);
    });

    // Initialize app logic once editor is ready
    initApp();
});

async function initApp() {
    try {
        // Get configurations (target file name etc)
        const confRes = await fetch('/api/config');
        state.config = await confRes.json();
        state.activeFile = state.config.target_file;
        document.getElementById('target-filename').textContent = state.activeFile;

        // Apply defaults from config file
        applyDefaults(state.config.defaults || {});

        // Load initial code and graph
        await syncWithDisk();

        // Initialize graph visualization canvas
        initializeGraph();

        // Connect to Server-Sent Events for live disk sync
        setupSSE();

        // Register event listeners
        registerToolbarListeners();
    } catch (err) {
        console.error("Initialization error", err);
        showBanner("Connection failed to Python backend. Is the server running?", "error");
    }
}

function setupSSE() {
    const eventSource = new EventSource('/api/events');
    const badge = document.getElementById('sync-status');
    const badgeText = document.getElementById('sync-status-text');

    eventSource.onopen = () => {
        badge.style.color = 'var(--emerald)';
        badge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
        badge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
        badgeText.textContent = 'Live Syncing';
        logMessage("📡 Connected to Python server. Event stream open.", "system");
    };

    eventSource.onmessage = async (event) => {
        if (event.data === 'updated') {
            showToast("🔄 Workspace file changed. Updating...");
            logMessage("🔄 Workspace file changed. Syncing code from disk...", "system");
            await syncWithDisk();
            return;
        }
        try {
            const payload = JSON.parse(event.data);
            if (payload && payload.type === 'file_parsed') {
                state.lastGraphData = payload;
                updateGraphViewDebounced(payload);
                showUpdateToast();
                
                const uCount = payload.nodes ? payload.nodes.filter(n => n.is_defined && !n.is_class && n.id !== '<module>').length : 0;
                logMessage(`✅ Parsed AST overlays successfully. Defined Functions: ${uCount}`, "info");

                // Acknowledge update processed to the backend
                fetch('/api/ack', { method: 'POST' }).catch(err => {
                    console.error("Ack failed", err);
                });
            }
        } catch (e) {
            // Ignore non-JSON or other message formats
        }
    };

    eventSource.onerror = (err) => {
        console.error("SSE Connection lost", err);
        badge.style.color = 'var(--rose)';
        badge.style.backgroundColor = 'rgba(244, 63, 94, 0.1)';
        badge.style.borderColor = 'rgba(244, 63, 94, 0.2)';
        badgeText.textContent = 'Offline';
        logMessage("❌ Server connection lost. Visualizer dashboard is offline.", "error");
    };
}

function registerToolbarListeners() {
    // Physics Toggle
    document.getElementById('toggle-physics-btn').addEventListener('click', function () {
        state.isPhysicsEnabled = !state.isPhysicsEnabled;
        if (state.isPhysicsEnabled) {
            this.classList.add('active');
            state.network.setOptions({ physics: { enabled: true } });
            showToast("⚙️ Physics simulation enabled");
        } else {
            this.classList.remove('active');
            state.network.setOptions({ physics: { enabled: false } });
            showToast("🚫 Physics simulation disabled");
        }
    });

    // Stable Layout Button Listener
    document.getElementById('stable-layout-btn').addEventListener('click', function () {
        startStabilization();
    });

    // Reset view/camera zoom
    document.getElementById('reset-view-btn').addEventListener('click', function () {
        if (state.network) {
            state.network.fit({ animation: { duration: 1000, easingFunction: 'easeInOutQuad' } });
            showToast("🔍 Reset view");
        }
    });

    // Layout Selector Changes
    document.getElementById('layout-select').addEventListener('change', function (e) {
        state.currentLayout = e.target.value;

        if (state.currentLayout === 'spring') {
            state.network.setOptions({
                layout: { hierarchical: { enabled: false } },
                physics: { enabled: state.isPhysicsEnabled }
            });
            showToast("🕸️ Switched to Spring layout");
        } else {
            const direction = state.currentLayout === 'hierarchical-tb' ? 'UD' : 'LR';
            state.network.setOptions({
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: direction,
                        sortMethod: 'directed',
                        nodeSpacing: 100,
                        treeSpacing: 100,
                        levelSpacing: 100
                    }
                },
                physics: { enabled: false }
            });
            showToast(`🌳 Switched to Hierarchical (${state.currentLayout === 'hierarchical-tb' ? 'Top-Down' : 'Left-Right'})`);
        }
    });

    // View Level Selector Changes (Function vs Module vs TensorBoard Graph)
    document.getElementById('view-level-select').addEventListener('change', function (e) {
        state.viewLevel = e.target.value;

        const colorSelect = document.getElementById('color-mode-select');

        if (state.viewLevel === 'module') {
            colorSelect.disabled = true;
            colorSelect.style.opacity = 0.5;
            showToast("📂 Switched to Module Graph");
        } else if (state.viewLevel === 'tensorboard') {
            colorSelect.disabled = true;
            colorSelect.style.opacity = 0.5;
            showToast("📊 Switched to TensorBoard Graph");
            const layoutSelect = document.getElementById('layout-select');
            layoutSelect.value = 'hierarchical-tb';
            state.currentLayout = 'hierarchical-tb';
            state.network.setOptions({
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'directed',
                        nodeSpacing: 100,
                        treeSpacing: 100,
                        levelSpacing: 100
                    }
                },
                physics: { enabled: false }
            });
        } else {
            colorSelect.disabled = false;
            colorSelect.style.opacity = 1.0;
            showToast("📂 Switched to Function Graph");
        }

        if (state.lastGraphData) {
            updateGraphView(state.lastGraphData);
        }
    });

    // Color Mode Selector Changes (Standard vs Complexity Heatmap)
    document.getElementById('color-mode-select').addEventListener('change', function (e) {
        state.activeColorMode = e.target.value;
        showToast(`🎨 Switched color theme to ${state.activeColorMode === 'complexity' ? 'Complexity Heatmap' : 'Standard Types'}`);
        if (state.lastGraphData) {
            updateGraphView(state.lastGraphData);
        }
    });

    // Export as PNG image
    document.getElementById('export-png-btn').addEventListener('click', function () {
        const canvas = document.querySelector('#network-canvas canvas');
        if (canvas) {
            const imgData = canvas.toDataURL("image/png");
            const link = document.createElement('a');
            link.download = `${state.config.target_file_basename || 'call_graph'}.png`;
            link.href = imgData;
            link.click();
            showToast("💾 Exported graph as PNG");
        } else {
            showToast("❌ Unable to export: Canvas not ready");
        }
    });

    // Force Decay (Damping) Slider Changes
    document.getElementById('decay-slider').addEventListener('input', function (e) {
        const val = parseFloat(e.target.value);
        document.getElementById('decay-value').textContent = val.toFixed(2);
        if (state.network) {
            state.network.setOptions({
                physics: {
                    barnesHut: {
                        damping: val
                    }
                }
            });
        }
    });

    // Toggle External Calls
    document.getElementById('toggle-external-btn').addEventListener('click', function () {
        state.showExternalCalls = !state.showExternalCalls;
        if (state.showExternalCalls) {
            this.classList.add('active');
            showToast("🔌 External library calls shown");
        } else {
            this.classList.remove('active');
            showToast("🧹 External library calls hidden");
        }
        if (state.lastGraphData) {
            updateGraphView(state.lastGraphData);
        }
    });

    // Live Node Search handler
    document.getElementById('search-input').addEventListener('input', function (e) {
        const query = e.target.value.toLowerCase().trim();
        if (!state.network) return;
        if (!query) {
            resetHighlight();
            state.network.selectNodes([]);
            return;
        }
        const matchedNode = state.nodesDataSet.get().find(n => n.id.toLowerCase().includes(query));
        if (matchedNode) {
            state.network.focus(matchedNode.id, {
                scale: 1.2,
                animation: { duration: 500, easingFunction: 'easeInOutQuad' }
            });
            state.network.selectNodes([matchedNode.id]);
            highlightNodeConnections(matchedNode.id);
        }
    });

    // Activity Bar Tab - Explorer Layout
    document.getElementById('btn-tab-explorer').addEventListener('click', function() {
        document.getElementById('btn-tab-explorer').classList.add('active');
        document.getElementById('btn-tab-analytics').classList.remove('active');
        
        const workspace = document.getElementById('workspace-splitter');
        workspace.className = 'workspace-area';
        
        const consoleBar = document.getElementById('bottom-console');
        consoleBar.classList.remove('open');
        state.isConsoleOpen = false;
        showToast("📂 Switched to Workspace layout");
    });

    // Activity Bar Tab - Analytics Layout
    document.getElementById('btn-tab-analytics').addEventListener('click', function() {
        document.getElementById('btn-tab-explorer').classList.remove('active');
        document.getElementById('btn-tab-analytics').classList.add('active');
        
        const workspace = document.getElementById('workspace-splitter');
        workspace.className = 'workspace-area maximized-graph';
        
        const consoleBar = document.getElementById('bottom-console');
        consoleBar.classList.add('open');
        state.isConsoleOpen = true;
        
        document.getElementById('tab-health').click();
        showToast("📊 Switched to Analytics & Health layout");
    });

    // Activity Bar Bottom - Toggle Console Icon
    document.getElementById('btn-toggle-console').addEventListener('click', function() {
        document.getElementById('btn-collapse-console').click();
    });

    // Maximize Editor (Hide Graph) toggle
    document.getElementById('btn-editor-split').addEventListener('click', function() {
        const workspace = document.getElementById('workspace-splitter');
        if (workspace.classList.contains('maximized-graph')) {
            workspace.className = 'workspace-area';
            showToast("🖥️ Split-screen mode");
        } else {
            workspace.className = 'workspace-area maximized-graph';
            showToast("🔍 Expanded call graph canvas");
        }
    });

    // Maximize Graph (Hide Editor) toggle
    document.getElementById('btn-graph-split').addEventListener('click', function() {
        const workspace = document.getElementById('workspace-splitter');
        if (workspace.classList.contains('maximized-editor')) {
            workspace.className = 'workspace-area';
            showToast("🖥️ Split-screen mode");
        } else {
            workspace.className = 'workspace-area maximized-editor';
            showToast("🔍 Expanded code editor panel");
        }
    });

    // Close Node Inspector Drawer
    document.getElementById('btn-close-inspector').addEventListener('click', function() {
        import('./ui.js').then(ui => ui.updateInspector(null));
        import('./graph.js').then(graph => graph.resetHighlight());
        if (state.network) {
            state.network.selectNodes([]);
        }
    });

    // Console Pane Switching
    ['health', 'metadata', 'logs'].forEach(tab => {
        document.getElementById(`tab-${tab}`).addEventListener('click', function() {
            ['health', 'metadata', 'logs'].forEach(t => {
                document.getElementById(`tab-${t}`).classList.remove('active');
                document.getElementById(`pane-${t}`).classList.remove('active');
            });
            this.classList.add('active');
            document.getElementById(`pane-${tab}`).classList.add('active');
            
            const consoleBar = document.getElementById('bottom-console');
            if (!state.isConsoleOpen) {
                consoleBar.classList.add('open');
                state.isConsoleOpen = true;
            }
        });
    });

    // Collapse / Expand Console Drawer
    document.getElementById('btn-collapse-console').addEventListener('click', function(e) {
        e.stopPropagation();
        const consoleBar = document.getElementById('bottom-console');
        state.isConsoleOpen = !state.isConsoleOpen;
        if (state.isConsoleOpen) {
            consoleBar.classList.add('open');
        } else {
            consoleBar.classList.remove('open');
        }
    });

    // Hotkey Ctrl + ` to toggle bottom console
    window.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === '`') {
            e.preventDefault();
            document.getElementById('btn-collapse-console').click();
        }
    });
}

function applyDefaults(defaults) {
    // 1. Libs (External Calls)
    if (defaults.libs === 'off' || defaults.libs === false) {
        state.showExternalCalls = false;
        document.getElementById('toggle-external-btn').classList.remove('active');
    } else {
        state.showExternalCalls = true;
        document.getElementById('toggle-external-btn').classList.add('active');
    }

    // 2. Physics
    if (defaults.physics === 'off' || defaults.physics === false) {
        state.isPhysicsEnabled = false;
        document.getElementById('toggle-physics-btn').classList.remove('active');
    } else {
        state.isPhysicsEnabled = true;
        document.getElementById('toggle-physics-btn').classList.add('active');
    }

    // 3. Layout Selector
    if (defaults.layout) {
        state.currentLayout = defaults.layout;
        document.getElementById('layout-select').value = defaults.layout;
    }

    // 4. View Level
    if (defaults.view) {
        state.viewLevel = defaults.view;
        document.getElementById('view-level-select').value = defaults.view;
        
        const colorSelect = document.getElementById('color-mode-select');
        if (state.viewLevel === 'module' || state.viewLevel === 'tensorboard') {
            colorSelect.disabled = true;
            colorSelect.style.opacity = 0.5;
        } else {
            colorSelect.disabled = false;
            colorSelect.style.opacity = 1.0;
        }
    }

    // 5. Color Mode
    if (defaults.color_mode) {
        state.activeColorMode = defaults.color_mode;
        document.getElementById('color-mode-select').value = defaults.color_mode;
    }
}
