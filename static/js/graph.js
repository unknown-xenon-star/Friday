import { state } from './state.js';
import { showToast, showBanner, hideBanner, updateInspector, updateConsoleStats, updateConsoleHealth } from './ui.js';
import { switchActiveFile } from './editor.js';

export function initializeGraph() {
    const container = document.getElementById('network-canvas');
    const data = {
        nodes: state.nodesDataSet,
        edges: state.edgesDataSet
    };

    const options = {
        nodes: {
            shape: 'dot',
            scaling: {
                min: 15,
                max: 30
            },
            font: {
                color: '#f3f4f6',
                size: 13,
                face: 'Inter',
                strokeWidth: 2,
                strokeColor: '#080c14'
            },
            borderWidth: 2,
            shadow: {
                enabled: true,
                color: 'rgba(0,0,0,0.5)',
                size: 5,
                x: 2,
                y: 2
            }
        },
        edges: {
            arrows: {
                to: {
                    enabled: true,
                    scaleFactor: 0.8
                }
            },
            color: {
                color: 'rgba(99, 102, 241, 0.4)',
                highlight: '#818cf8',
                hover: '#818cf8',
                inherit: false
            },
            width: 2,
            smooth: {
                enabled: true,
                type: 'cubicBezier',
                roundness: 0.5
            }
        },
        physics: {
            enabled: state.isPhysicsEnabled,
            barnesHut: {
                gravitationalConstant: -2000,
                centralGravity: 0.1,
                springLength: 95,
                springConstant: 0.01,
                damping: 0.85,
                avoidOverlap: 1
            },
            stabilization: {
                enabled: true,
                iterations: 1000,
                fit: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100
        }
    };

    state.network = new vis.Network(container, data, options);

    // Double Click node to scroll Monaco editor to code definition
    state.network.on("doubleClick", function (params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            if (state.viewLevel === 'module') {
                if (nodeId !== 'External') {
                    const targetFile = nodeId.replace(/\./g, '/') + '.py';
                    switchActiveFile(targetFile);
                } else {
                    showToast(`ℹ️ External Libraries has no single file definitions`);
                }
                return;
            }

            const node = state.nodesDataSet.get(nodeId);
            if (node) {
                if (node.filepath && node.filepath !== state.activeFile) {
                    // Target is in a different file - load it first
                    switchActiveFile(node.filepath, node.lineno);
                } else if (node.lineno) {
                    // Target is in current file - jump immediately
                    state.editor.revealLineInCenter(node.lineno);
                    state.editor.setPosition({ lineNumber: node.lineno, column: 1 });
                    state.editor.focus();
                    showToast(`📍 Jumped to definition of <code>${nodeId}</code> on line ${node.lineno}`);
                } else {
                    showToast(`ℹ️ <code>${nodeId}</code> is an external library call (no definition in project)`);
                }
            }
        }
    });

    // Node Selection path highlight
    state.network.on("selectNode", function (params) {
        if (params.nodes.length > 0) {
            highlightNodeConnections(params.nodes[0]);
            const node = state.nodesDataSet.get(params.nodes[0]);
            if (node) {
                updateInspector(node);
            }
        }
    });

    // Node Deselection reset highlight
    state.network.on("deselectNode", function (params) {
        resetHighlight();
        updateInspector(null);
    });

    // Layout Stabilization Listeners
    state.network.on("stabilizationProgress", function (params) {
        if (state.isStabilizing) {
            let progress = Math.round((params.iterations / params.total) * 100);
            document.getElementById('stabilization-progress-bar').style.width = progress + '%';
            document.getElementById('stabilization-progress-text').textContent = progress + '%';
        }
    });

    state.network.on("stabilizationIterationsDone", function () {
        if (state.isStabilizing) {
            finishStabilization();
        }
    });

    state.network.on("stabilized", function () {
        if (state.isStabilizing) {
            finishStabilization();
        }
    });
}

// Render Graph Data using vis-network
export function updateGraphView(graphData) {
    // Save reference to raw graph data for local switching/filtering
    state.lastGraphData = graphData;

    if (graphData.error) {
        showBanner(graphData.error, "error");
        return;
    } else {
        hideBanner();
    }



    // Automatically pause physics during batch background updates to save user's CPU and prevent UI freezing
    const pendingCount = typeof graphData.pending_updates === 'number' ? graphData.pending_updates : 0;
    if (pendingCount > 0) {
        if (state.network && state.currentLayout === 'spring') {
            state.network.setOptions({ physics: { enabled: false } });
        }
    } else {
        if (state.network && state.currentLayout === 'spring' && state.isPhysicsEnabled) {
            state.network.setOptions({ physics: { enabled: true } });
        }
    }

    // Filter and aggregate nodes and edges
    let filteredNodes = graphData.nodes;
    let filteredEdges = graphData.edges;

    if (state.viewLevel === 'tensorboard') {
        const modelGraph = graphData.model_graph || { nodes: [], edges: [] };
        filteredNodes = modelGraph.nodes;
        filteredEdges = modelGraph.edges;
    } else if (state.viewLevel === 'module') {
        // Aggregate function-level nodes to file/module-level nodes
        const moduleMap = {};
        
        graphData.nodes.forEach(node => {
            const mod = node.module_prefix || 'External';
            // Hide external libraries at module level if libs toggle is inactive
            if (!state.showExternalCalls && mod === 'External') {
                return;
            }
            
            if (!moduleMap[mod]) {
                moduleMap[mod] = {
                    id: mod,
                    label: mod === 'External' ? 'External Libraries' : `${mod}.py`,
                    is_defined: mod !== 'External',
                    is_class: false,
                    is_module: true,
                    functionsCount: 0,
                    classesCount: 0,
                    totalLoc: 0,
                    totalComplexity: 0
                };
            }
            
            if (node.is_defined) {
                if (node.is_class) {
                    moduleMap[mod].classesCount++;
                } else if (!node.id.endsWith('.<module>')) {
                    moduleMap[mod].functionsCount++;
                }
                if (node.loc) moduleMap[mod].totalLoc += node.loc;
                if (node.complexity) moduleMap[mod].totalComplexity += node.complexity;
            }
        });
        
        filteredNodes = Object.values(moduleMap);
        
        const moduleEdgesMap = {};
        const nodeLookup = new Map();
        graphData.nodes.forEach(n => nodeLookup.set(n.id, n));

        graphData.edges.forEach(edge => {
            const fromNode = nodeLookup.get(edge.from);
            const toNode = nodeLookup.get(edge.to);
            if (!fromNode || !toNode) return;
            
            const fromMod = fromNode.module_prefix || 'External';
            const toMod = toNode.module_prefix || 'External';
            
            if (!state.showExternalCalls && (fromMod === 'External' || toMod === 'External')) {
                return;
            }
            
            if (fromMod !== toMod) {
                const edgeKey = `${fromMod}->${toMod}`;
                if (!moduleEdgesMap[edgeKey]) {
                    moduleEdgesMap[edgeKey] = {
                        from: fromMod,
                        to: toMod,
                        value: 0,
                        type: 'call'
                    };
                }
                moduleEdgesMap[edgeKey].value += edge.value;
            }
        });
        
        filteredEdges = Object.values(moduleEdgesMap);
    } else {
        // Function level filtering
        if (!state.showExternalCalls) {
            filteredNodes = graphData.nodes.filter(node => node.is_defined || node.id === '<module>');
            const activeNodeIdsSet = new Set(filteredNodes.map(n => n.id));
            filteredEdges = graphData.edges.filter(edge =>
                activeNodeIdsSet.has(edge.from) && activeNodeIdsSet.has(edge.to)
            );
        }
    }

    // Map server nodes to vis format with styling
    const styledNodes = filteredNodes.map(node => {
        if (state.viewLevel === 'tensorboard') {
            let bgColor = '#475569'; // default slate-600
            let borderColor = '#64748b';
            let highlightBg = '#334155';
            let highlightBorder = '#94a3b8';
            
            const lType = (node.layer_type || '').toLowerCase();
            
            if (lType === 'input') {
                bgColor = '#10b981'; // Emerald-500
                borderColor = '#34d399'; // Emerald-400
                highlightBg = '#059669';
                highlightBorder = '#6ee7b7';
            } else if (lType.includes('dense') || lType.includes('linear')) {
                bgColor = '#3b82f6'; // Blue-500
                borderColor = '#60a5fa'; // Blue-400
                highlightBg = '#2563eb';
                highlightBorder = '#93c5fd';
            } else if (lType.includes('conv') || lType.includes('pool')) {
                bgColor = '#f97316'; // Orange-500
                borderColor = '#fb923c'; // Orange-400
                highlightBg = '#ea580c';
                highlightBorder = '#ffedd5';
            } else if (lType.includes('rnn') || lType.includes('lstm') || lType.includes('gru')) {
                bgColor = '#0d9488'; // Teal-600
                borderColor = '#14b8a6'; // Teal-500
                highlightBg = '#0f766e';
                highlightBorder = '#99f6e4';
            } else if (lType.includes('dropout') || lType.includes('flatten') || lType.includes('reshape') || lType.includes('embedding')) {
                bgColor = '#64748b'; // Slate-500
                borderColor = '#94a3b8'; // Slate-400
                highlightBg = '#475569';
                highlightBorder = '#cbd5e1';
            } else if (lType.includes('activation') || lType.includes('norm')) {
                bgColor = '#6366f1'; // Indigo-500
                borderColor = '#818cf8'; // Indigo-400
                highlightBg = '#4f46e5';
                highlightBorder = '#a5b4fc';
            } else if (['add', 'multiply', 'matmul', 'reduce', 'concat', 'concatenate', 'maximum', 'minimum', 'average'].some(op => lType.includes(op))) {
                bgColor = '#8b5cf6'; // Violet-500
                borderColor = '#a78bfa'; // Violet-400
                highlightBg = '#7c3aed';
                highlightBorder = '#c4b5fd';
            }
            
            let title = `<b>${node.id}</b>`;
            title += `<br/>Layer Type: <b>${node.layer_type}</b>`;
            if (node.output_shape) {
                title += `<br/>Output Shape: <b>${node.output_shape}</b>`;
            }
            if (node.parameters) {
                title += `<br/>Parameters: <code>${node.parameters}</code>`;
            }
            if (node.lineno) {
                title += `<br/>Defined on Line <b>${node.lineno}</b>`;
            }
            
            return {
                id: node.id,
                label: `${node.label}\n${node.output_shape || ''}`,
                filepath: node.filepath,
                lineno: node.lineno,
                shape: 'box',
                margin: { top: 10, bottom: 10, left: 15, right: 15 },
                title: title,
                color: {
                    background: bgColor,
                    border: borderColor,
                    highlight: { background: highlightBg, border: highlightBorder },
                    hover: { background: highlightBg, border: highlightBorder }
                },
                font: { color: '#ffffff', face: 'JetBrains Mono', size: 12, bold: true },
                shadow: { enabled: true, color: 'rgba(0,0,0,0.3)', size: 4, x: 2, y: 2 }
            };
        }
        
        if (state.viewLevel === 'module') {
            const isExternal = node.id === 'External';
            let bgColor = '#8b5cf6'; // Violet-500
            let borderColor = '#a78bfa'; // Violet-400
            let highlightBg = '#7c3aed'; // Violet-600
            let highlightBorder = '#c4b5fd';
            
            if (isExternal) {
                bgColor = '#475569';
                borderColor = '#64748b';
                highlightBg = '#334155';
                highlightBorder = '#94a3b8';
            }
            
            let title = `<b>${isExternal ? 'External Libraries' : node.id + '.py'}</b>`;
            if (!isExternal) {
                title += `<br/>Defined Classes: <b>${node.classesCount}</b>`;
                title += `<br/>Defined Functions: <b>${node.functionsCount}</b>`;
                title += `<br/>Total Lines of Code: <b>${node.totalLoc}</b>`;
                title += `<br/>Accumulated Complexity: <b>${node.totalComplexity}</b>`;
            } else {
                title += `<br/>Imports and external packages used by the project`;
            }
            
            return {
                id: node.id,
                label: node.label,
                shape: 'box',
                margin: 10,
                title: title,
                color: {
                    background: bgColor,
                    border: borderColor,
                    highlight: { background: highlightBg, border: highlightBorder },
                    hover: { background: highlightBg, border: highlightBorder }
                },
                font: { color: '#f3f4f6', face: 'Inter', size: 14, bold: true },
                shadow: { enabled: true, color: 'rgba(0,0,0,0.3)', size: 4, x: 2, y: 2 }
            };
        }

        const isUserDefined = node.is_defined;
        const isClass = node.is_class;

        let bgColor = '#334155'; // default external
        let borderColor = '#475569';
        let highlightBg = '#475569';
        let highlightBorder = '#64748b';
        let borderDashes = false;

        if (state.activeColorMode === 'complexity' && isUserDefined && !isClass && node.id !== '<module>') {
            // Heatmap colors based on function complexity
            const c = node.complexity || 1;
            if (c > 7) {
                bgColor = '#ef4444'; // Red-500 (Complex)
                borderColor = '#f87171'; // Red-400
                highlightBg = '#dc2626';
                highlightBorder = '#fca5a5';
            } else if (c >= 4) {
                bgColor = '#f59e0b'; // Amber-500 (Moderate)
                borderColor = '#fbbf24'; // Amber-400
                highlightBg = '#d97706';
                highlightBorder = '#fcd34d';
            } else {
                bgColor = '#3b82f6'; // Blue-500 (Simple)
                borderColor = '#60a5fa'; // Blue-400
                highlightBg = '#2563eb';
                highlightBorder = '#93c5fd';
            }
        } else {
            if (node.id === '<module>') {
                bgColor = '#1e293b'; // dark entry
                borderColor = '#64748b';
                highlightBg = '#334155';
                highlightBorder = '#94a3b8';
            } else if (isClass) {
                bgColor = '#059669'; // Emerald-600
                borderColor = '#10b981'; // Emerald-500
                highlightBg = '#047857';
                highlightBorder = '#34d399';
            } else if (isUserDefined) {
                bgColor = '#6366f1'; // Indigo-500
                borderColor = '#818cf8'; // Indigo-400
                highlightBg = '#4f46e5';
                highlightBorder = '#a5b4fc';

                // Highlight unused / dead functions
                if (node.is_unused) {
                    borderColor = '#f43f5e'; // rose-500
                    highlightBorder = '#f43f5e';
                    borderDashes = true;
                }
            }
        }

        let shape = 'diamond';
        if (node.id === '<module>') {
            shape = 'circle';
        } else if (isClass) {
            shape = 'box';
        } else if (isUserDefined) {
            shape = 'dot';
        }

        let title = `<b>${node.id === '<module>' ? 'Module Entry Point' : node.id}</b>`;
        if (node.id === '<module>') {
            title += `<br/>Top-level code execution flow`;
        } else if (isClass) {
            title += `<br/>Class definition (Line ${node.lineno})`;
            if (node.loc) title += `<br/>Lines of Code: <b>${node.loc}</b>`;
            if (node.complexity) title += `<br/>Complexity Index: <b>${node.complexity}</b>`;
        } else if (isUserDefined) {
            if (node.is_unused) {
                title += `<br/><span style="color: #f43f5e; font-weight: bold;">⚠️ Unused Function / Dead Code</span>`;
            }
            title += `<br/>User defined function (Line ${node.lineno})`;
            if (node.loc) {
                const warning = node.loc > 50 ? ' <span style="color: #f43f5e; font-weight: bold;">(Long function)</span>' : '';
                title += `<br/>Lines of Code: <b>${node.loc}</b>${warning}`;
            }
            if (node.complexity) {
                const warning = node.complexity > 7 ? ' <span style="color: #ef4444; font-weight: bold;">⚠️ High complexity</span>' : '';
                title += `<br/>Complexity Index: <b>${node.complexity}</b>${warning}`;
            }
        } else {
            title += `<br/>External library call`;
        }

        if (node.decorators && node.decorators.length > 0) {
            title += `<br/>Decorators: ` + node.decorators.map(d => `@${d}`).join(', ');
        }

        return {
            id: node.id,
            label: node.id === '<module>' ? 'Entrypoint' : node.label,
            lineno: node.lineno,
            color: {
                background: bgColor,
                border: borderColor,
                highlight: {
                    background: highlightBg,
                    border: highlightBorder
                },
                hover: {
                    background: highlightBg,
                    border: highlightBorder
                }
            },
            borderWidth: isUserDefined || isClass ? 2 : 1,
            shape: shape,
            shapeProperties: {
                borderDashes: borderDashes
            },
            size: node.id === '<module>' ? 18 : (isClass ? 26 : (isUserDefined ? 24 : 14)),
            shadow: isUserDefined || isClass ? { enabled: true, color: isClass ? 'rgba(16, 185, 129, 0.4)' : 'rgba(99, 102, 241, 0.4)', size: 10 } : { enabled: false },
            title: title
        };
    });

    // Map server edges to vis format
    const styledEdges = filteredEdges.map(edge => {
        if (state.viewLevel === 'tensorboard') {
            return {
                from: edge.from,
                to: edge.to,
                label: edge.tensor_shape || '',
                font: { size: 10, color: '#9ca3af', face: 'JetBrains Mono', align: 'horizontal', background: '#080c14' },
                color: {
                    color: 'rgba(148, 163, 184, 0.6)',
                    highlight: '#38bdf8',
                    hover: '#38bdf8',
                    inherit: false
                },
                width: 2.5,
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 0.8
                    }
                },
                smooth: {
                    enabled: true,
                    type: 'cubicBezier',
                    roundness: 0.3
                },
                title: `Tensor flow: ${edge.tensor_shape || 'unknown shape'}`
            };
        }

        const isDecorator = edge.type === 'decorator';
        const isContainment = edge.type === 'containment';

        let color = 'rgba(99, 102, 241, 0.4)'; // default call: indigo
        let highlightColor = '#818cf8';
        if (isDecorator) {
            color = 'rgba(234, 179, 8, 0.5)'; // gold
            highlightColor = '#eab308';
        } else if (isContainment) {
            color = 'rgba(148, 163, 184, 0.25)'; // subtle slate-400
            highlightColor = '#94a3b8';
        }

        return {
            from: edge.from,
            to: edge.to,
            value: isDecorator || isContainment ? 1 : edge.value,
            dashes: isDecorator || isContainment,
            arrows: {
                to: {
                    enabled: !isContainment, // no arrows for containment edges
                    scaleFactor: 0.8
                }
            },
            label: isDecorator ? 'decorates' : (isContainment ? 'defines' : ''),
            font: { size: 9, color: '#6b7280', strokeWidth: 0 },
            color: {
                color: color,
                highlight: highlightColor,
                hover: highlightColor,
                inherit: false
            },
            width: isDecorator || isContainment ? 1 : 2,
            smooth: {
                enabled: true,
                type: 'cubicBezier',
                roundness: 0.5
            },
            title: isDecorator
                ? `Decorates function`
                : (isContainment ? `Defines structural method` : `Called ${edge.value} time(s)`)
        };
    });

    // Update data set smoothly
    const prevNodeIds = state.nodesDataSet.getIds();
    const newNodeIdsSet = new Set(styledNodes.map(n => n.id));

    // Remove nodes not in new graph
    prevNodeIds.forEach(id => {
        if (!newNodeIdsSet.has(id)) {
            state.nodesDataSet.remove(id);
        }
    });

    // Add or update current nodes
    styledNodes.forEach(node => {
        state.nodesDataSet.update(node);
    });

    // Update edges smoothly by diffing
    const prevEdgeIds = state.edgesDataSet.getIds();
    styledEdges.forEach(e => {
        e.id = `${e.from}->${e.to}->${e.type || ''}`;
    });
    const newEdgeIdsSet = new Set(styledEdges.map(e => e.id));

    // Remove edges not in the new graph
    prevEdgeIds.forEach(id => {
        if (!newEdgeIdsSet.has(id)) {
            state.edgesDataSet.remove(id);
        }
    });

    // Add or update current edges
    styledEdges.forEach(edge => {
        state.edgesDataSet.update(edge);
    });

    // Update bottom panel diagnostics
    updateConsoleStats(graphData);
    updateConsoleHealth(graphData);
}

let pendingUpdatePayload = null;
let updateTimeout = null;

export function updateGraphViewDebounced(graphData) {
    pendingUpdatePayload = graphData;
    if (!updateTimeout) {
        updateTimeout = setTimeout(() => {
            if (pendingUpdatePayload) {
                updateGraphView(pendingUpdatePayload);
                pendingUpdatePayload = null;
            }
            updateTimeout = null;
        }, 100);
    }
}

// Upstream/Downstream Node Connection Highlighting (Focus Mode)
export function highlightNodeConnections(nodeId) {
    const allNodes = state.nodesDataSet.get();
    const allEdges = state.edgesDataSet.get();

    const upstreamNodes = new Set();
    const downstreamNodes = new Set();

    // Group edges by their endpoints for fast O(1) traversals
    const edgesByTo = new Map();
    const edgesByFrom = new Map();
    allEdges.forEach(edge => {
        const to = edge.to;
        const from = edge.from;
        if (!edgesByTo.has(to)) edgesByTo.set(to, []);
        edgesByTo.get(to).push(edge);

        if (!edgesByFrom.has(from)) edgesByFrom.set(from, []);
        edgesByFrom.get(from).push(edge);
    });

    // Recurse to trace upstream callers
    function traceUpstream(id) {
        const incoming = edgesByTo.get(id) || [];
        incoming.forEach(edge => {
            if (!upstreamNodes.has(edge.from)) {
                upstreamNodes.add(edge.from);
                traceUpstream(edge.from);
            }
        });
    }

    // Recurse to trace downstream callees
    function traceDownstream(id) {
        const outgoing = edgesByFrom.get(id) || [];
        outgoing.forEach(edge => {
            if (!downstreamNodes.has(edge.to)) {
                downstreamNodes.add(edge.to);
                traceDownstream(edge.to);
            }
        });
    }

    traceUpstream(nodeId);
    traceDownstream(nodeId);

    const activeNodes = new Set([nodeId, ...upstreamNodes, ...downstreamNodes]);

    // Update nodes styling - fade out inactive nodes
    const updatedNodes = allNodes.map(n => {
        const isActive = activeNodes.has(n.id);
        const opacity = isActive ? 1.0 : 0.15;

        // Extract colors safely
        const origColor = n.color || { background: '#6366f1', border: '#818cf8' };
        const bgColor = adjustOpacity(origColor.background || origColor, opacity);
        const borderColor = adjustOpacity(origColor.border || origColor, opacity);
        const textColor = adjustOpacity('#f3f4f6', opacity);

        return {
            id: n.id,
            color: {
                background: bgColor,
                border: borderColor,
                highlight: { background: bgColor, border: borderColor },
                hover: { background: bgColor, border: borderColor }
            },
            font: { color: textColor },
            shadow: isActive ? n.shadow : { enabled: false }
        };
    });

    // Update edges styling - fade out inactive edges
    const updatedEdges = allEdges.map(e => {
        const isEdgeActive = activeNodes.has(e.from) && activeNodes.has(e.to) &&
            ((upstreamNodes.has(e.from) && (upstreamNodes.has(e.to) || e.to === nodeId)) ||
                ((downstreamNodes.has(e.to) || e.to === nodeId) && downstreamNodes.has(e.from)) ||
                (e.from === nodeId && downstreamNodes.has(e.to)) ||
                (e.to === nodeId && upstreamNodes.has(e.from)));

        const opacity = isEdgeActive ? 1.0 : 0.08;
        const origColor = e.color || { color: 'rgba(99,102,241,0.4)' };
        const edgeColor = adjustOpacity(origColor.color || origColor, opacity);

        return {
            id: e.id,
            color: {
                color: edgeColor,
                highlight: edgeColor,
                hover: edgeColor
            }
        };
    });

    state.nodesDataSet.update(updatedNodes);
    state.edgesDataSet.update(updatedEdges);
}

export function resetHighlight() {
    if (state.lastGraphData) {
        updateGraphView(state.lastGraphData);
    }
}

export function adjustOpacity(colorStr, opacity) {
    if (!colorStr) return colorStr;
    if (typeof colorStr === 'object') {
        colorStr = colorStr.background || colorStr.color || '#6366f1';
    }
    if (colorStr.startsWith('rgba')) {
        return colorStr.replace(/[\d\.]+\)$/, `${opacity})`);
    }
    if (colorStr.startsWith('rgb')) {
        return colorStr.replace('rgb', 'rgba').replace(')', `, ${opacity})`);
    }
    if (colorStr.startsWith('#')) {
        const hex = colorStr.replace('#', '');
        let r, g, b;
        if (hex.length === 3) {
            r = parseInt(hex[0] + hex[0], 16);
            g = parseInt(hex[1] + hex[1], 16);
            b = parseInt(hex[2] + hex[2], 16);
        } else {
            r = parseInt(hex.substring(0, 2), 16);
            g = parseInt(hex.substring(2, 4), 16);
            b = parseInt(hex.substring(4, 6), 16);
        }
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
    return colorStr;
}



export function startStabilization() {
    if (state.isStabilizing) return;
    state.isStabilizing = true;
    
    // Remember original physics state
    state.preStabilizationPhysicsState = state.isPhysicsEnabled;
    
    // Show overlay, reset progress
    document.getElementById('stabilization-progress-bar').style.width = '0%';
    document.getElementById('stabilization-progress-text').textContent = '0%';
    document.getElementById('stabilization-overlay').style.display = 'flex';
    
    // Temporarily enable physics and set stabilization iterations
    state.network.setOptions({
        physics: {
            enabled: true,
            stabilization: {
                enabled: true,
                iterations: 1000,
                fit: true
            }
        }
    });
    
    // Run stabilization iterations
    state.network.stabilize(1000);
}

export function finishStabilization() {
    if (!state.isStabilizing) return;
    state.isStabilizing = false;
    
    // Hide overlay
    document.getElementById('stabilization-overlay').style.display = 'none';
    
    // Revert physics configuration
    state.network.setOptions({
        physics: {
            enabled: state.preStabilizationPhysicsState
        }
    });
    
    showToast("✨ Graph layout stabilized successfully");
}
