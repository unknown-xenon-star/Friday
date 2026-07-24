import { state } from './state.js';

export function showBanner(message, type) {
    const banner = document.getElementById('notify-banner');
    const text = document.getElementById('notify-text');

    banner.className = `notification-banner ${type}`;
    text.innerHTML = message.replace(/\n/g, '<br/>');
    banner.classList.add('show');
}

export function hideBanner() {
    const banner = document.getElementById('notify-banner');
    banner.classList.remove('show');
}

export function showToast(message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse forwards';
        setTimeout(() => {
            if (container.contains(toast)) {
                container.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

export function showUpdateToast() {
    const container = document.getElementById('toast-container');
    if (state.activeUpdateToast && container.contains(state.activeUpdateToast)) {
        state.updateToastCount++;
        state.activeUpdateToast.innerHTML = `📂 Added next function/node to graph (+${state.updateToastCount})`;
        
        clearTimeout(state.updateToastTimer);
        state.updateToastTimer = setTimeout(() => {
            const toastToDismiss = state.activeUpdateToast;
            toastToDismiss.style.animation = 'slideIn 0.3s ease reverse forwards';
            setTimeout(() => {
                if (container.contains(toastToDismiss)) {
                    container.removeChild(toastToDismiss);
                }
            }, 300);
            state.activeUpdateToast = null;
            state.updateToastCount = 0;
        }, 3000);
    } else {
        state.updateToastCount = 0;
        state.activeUpdateToast = document.createElement('div');
        state.activeUpdateToast.className = 'toast';
        state.activeUpdateToast.innerHTML = `📂 Added next function/node to graph`;
        container.appendChild(state.activeUpdateToast);

        state.updateToastTimer = setTimeout(() => {
            const toastToDismiss = state.activeUpdateToast;
            toastToDismiss.style.animation = 'slideIn 0.3s ease reverse forwards';
            setTimeout(() => {
                if (container.contains(toastToDismiss)) {
                    container.removeChild(toastToDismiss);
                }
            }, 300);
            state.activeUpdateToast = null;
            state.updateToastCount = 0;
        }, 3000);
    }
}

export function updateInspector(node) {
    const drawer = document.getElementById('inspector-drawer');
    const content = document.getElementById('inspector-content');
    
    state.selectedNode = node;
    
    if (!node) {
        content.innerHTML = `<div class="empty-state">Select a node in the graph to inspect static metrics, class definition coordinates, complexity scales, and decoration scopes.</div>`;
        drawer.classList.remove('open');
        return;
    }
    
    drawer.classList.add('open');
    
    // Determine node classification type
    let typeLabel = "External Library Call";
    if (node.id === '<module>') {
        typeLabel = "Module Entry Point";
    } else if (node.is_class) {
        typeLabel = "Class Definition";
    } else if (node.is_defined) {
        typeLabel = node.is_unused ? "Unused Function (Dead Code)" : "User Defined Function";
    }

    // Header layout
    let html = `
        <div class="inspector-title-card">
            <div class="inspector-node-name">${node.id}</div>
            <div class="inspector-node-type" style="color: ${node.is_class ? 'var(--emerald)' : (node.is_unused ? 'var(--rose)' : 'var(--accent-color)')}">${typeLabel}</div>
        </div>
    `;

    // File path info
    if (node.filepath) {
        html += `
            <div class="inspector-section-title">Location</div>
            <div class="meta-list">
                <div class="meta-item">
                    <span class="meta-lbl">File</span>
                    <span class="meta-val">${node.filepath.split('/').pop()}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-lbl">Line Number</span>
                    <span class="meta-val">${node.lineno || 'N/A'}</span>
                </div>
                <button class="warning-action-btn" style="width: 100%; margin-top: 0.5rem; text-align: center; display: block;" id="inspector-jump-btn">
                    Jump to Definition
                </button>
            </div>
        `;
    }

    // Radial Code Volume LOC Gauge
    if (node.loc) {
        const maxLoc = 100;
        const pct = Math.min(100, Math.round((node.loc / maxLoc) * 100));
        const circ = 125.6; // 2 * pi * r (r=20)
        const strokeOffset = circ - (pct / 100) * circ;

        html += `
            <div class="inspector-section-title">Code Volume</div>
            <div class="gauge-container">
                <div class="gauge-circle-wrapper">
                    <svg width="48" height="48" viewBox="0 0 48 48">
                        <circle class="gauge-circle-bg" cx="24" cy="24" r="20" />
                        <circle class="gauge-circle-fill" cx="24" cy="24" r="20" 
                                stroke="${node.loc > 50 ? 'var(--rose)' : 'var(--accent-color)'}"
                                stroke-dasharray="${circ}"
                                stroke-dashoffset="${strokeOffset}" />
                    </svg>
                    <div class="gauge-text">${node.loc}</div>
                </div>
                <div class="gauge-details">
                    <div class="gauge-label">${node.loc} Lines of Code</div>
                    <div class="gauge-desc">${node.loc > 50 ? '⚠️ Consider refactoring (long)' : 'Optimal line length'}</div>
                </div>
            </div>
        `;
    }

    // Complexity indicator
    if (node.complexity) {
        const maxComp = 15;
        const pct = Math.min(100, Math.round((node.complexity / maxComp) * 100));
        let compColor = 'var(--emerald)';
        let compDesc = 'Simple logic (clean)';
        
        if (node.complexity > 7) {
            compColor = 'var(--rose)';
            compDesc = 'High complexity (needs review)';
        } else if (node.complexity >= 4) {
            compColor = '#f59e0b';
            compDesc = 'Moderate complexity';
        }

        html += `
            <div class="inspector-section-title">Cyclomatic Complexity</div>
            <div class="complexity-bar-container">
                <div class="complexity-lbl-row">
                    <span class="complexity-lbl-text">Index: ${node.complexity}</span>
                    <span class="complexity-level-desc" style="color: ${compColor}">${compDesc}</span>
                </div>
                <div class="complexity-track">
                    <div class="complexity-fill" style="width: ${pct}%; background-color: ${compColor};"></div>
                </div>
            </div>
        `;
    }

    // Decorators list
    if (node.decorators && node.decorators.length > 0) {
        html += `
            <div class="inspector-section-title">Decorators</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.25rem;">
                ${node.decorators.map(dec => `<span style="background: rgba(234,179,8,0.1); border: 1px solid rgba(234,179,8,0.2); color: #eab308; font-size: 0.75rem; padding: 0.15rem 0.45rem; border-radius: 9999px; font-family: var(--font-mono)">@${dec}</span>`).join('')}
            </div>
        `;
    }

    content.innerHTML = html;

    // Bind jump button action
    const jumpBtn = document.getElementById('inspector-jump-btn');
    if (jumpBtn) {
        jumpBtn.addEventListener('click', async () => {
            const { switchActiveFile } = await import('./editor.js');
            switchActiveFile(node.filepath, node.lineno);
        });
    }
}

export function updateConsoleHealth(graphData) {
    const container = document.getElementById('pane-health');
    if (!graphData || !graphData.nodes) {
        container.innerHTML = `<div class="health-empty-state">No compiled code warnings. Type or save python files to initiate scanning.</div>`;
        return;
    }

    const warnings = [];

    graphData.nodes.forEach(node => {
        if (!node.is_defined || node.is_class || node.id === '<module>') return;

        if (node.is_unused) {
            warnings.push({
                type: 'unused',
                icon: '⚠️',
                msg: 'Unused / dead function code',
                target: node.id,
                node: node
            });
        }

        if (node.complexity && node.complexity > 7) {
            warnings.push({
                type: 'complexity',
                icon: '🔥',
                msg: `High complexity hotspot (${node.complexity})`,
                target: node.id,
                node: node
            });
        }
    });

    if (warnings.length === 0) {
        container.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--emerald); gap: 0.5rem; margin-top: 1.5rem;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 2rem; height: 2rem;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <span style="font-weight: 600; font-size: 0.9rem;">Clean Bill of Health! No warnings or bottlenecks found.</span>
            </div>
        `;
        return;
    }

    let html = `<div class="warning-card-list">`;
    warnings.forEach((w, idx) => {
        html += `
            <div class="warning-card ${w.type}">
                <div class="warning-details">
                    <span class="warning-icon">${w.icon}</span>
                    <span class="warning-msg">${w.msg}</span>
                    <span class="warning-target">${w.target}</span>
                </div>
                <button class="warning-action-btn" id="warning-jump-btn-${idx}">Inspect</button>
            </div>
        `;
    });
    html += `</div>`;
    container.innerHTML = html;

    // Bind warning actions
    warnings.forEach((w, idx) => {
        document.getElementById(`warning-jump-btn-${idx}`).addEventListener('click', async () => {
            const { switchActiveFile } = await import('./editor.js');
            await switchActiveFile(w.node.filepath, w.node.lineno);
            updateInspector(w.node);
            
            if (state.network && w.node.id) {
                state.network.focus(w.node.id, {
                    scale: 1.2,
                    animation: { duration: 600, easingFunction: 'easeInOutQuad' }
                });
                state.network.selectNodes([w.node.id]);
                const { highlightNodeConnections } = await import('./graph.js');
                highlightNodeConnections(w.node.id);
            }
        });
    });
}

export function updateConsoleStats(graphData) {
    if (!graphData || !graphData.nodes) return;

    let totalLoc = 0;
    let classCount = 0;
    let funcCount = 0;
    let complexitySum = 0;
    let complexityCount = 0;

    graphData.nodes.forEach(node => {
        if (!node.is_defined || node.id === '<module>') return;

        if (node.is_class) {
            classCount++;
        } else {
            funcCount++;
        }

        if (node.loc) totalLoc += node.loc;
        if (node.complexity) {
            complexitySum += node.complexity;
            complexityCount++;
        }
    });

    const avgComplexity = complexityCount > 0 ? (complexitySum / complexityCount).toFixed(1) : '0.0';

    document.getElementById('stat-total-loc').textContent = totalLoc;
    document.getElementById('stat-class-count').textContent = classCount;
    document.getElementById('stat-func-count').textContent = funcCount;
    document.getElementById('stat-avg-complexity').textContent = avgComplexity;
}

export function logMessage(message, type = 'info') {
    const stream = document.getElementById('logs-stream-content');
    if (!stream) return;
    
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `[${time}] ${message}`;
    stream.appendChild(line);
    
    // Maintain maximum logs inside viewport buffer
    if (stream.children.length > 100) {
        stream.removeChild(stream.firstChild);
    }
    
    stream.scrollTop = stream.scrollHeight;
}

export function isSamePath(pathA, pathB) {
    if (!pathA || !pathB) return false;
    const clean = p => p.toLowerCase()
                        .replace(/\\/g, '/')
                        .replace(/^\.\//, '')
                        .replace(/^\//, '');
    const a = clean(pathA);
    const b = clean(pathB);
    return a === b || a.endsWith('/' + b) || b.endsWith('/' + a);
}

export function renderFileExplorer() {
    const listContainer = document.getElementById('explorer-file-list');
    if (!listContainer) return;

    listContainer.innerHTML = '';
    
    if (state.filteredFiles.length === 0) {
        listContainer.innerHTML = `<div style="padding: 1rem; font-size: 0.78rem; color: var(--text-secondary); text-align: center;">No python files found</div>`;
        return;
    }

    state.filteredFiles.forEach(file => {
        const item = document.createElement('div');
        const isActive = isSamePath(file, state.activeFile);
        item.className = `explorer-file-item ${isActive ? 'active' : ''}`;
        
        // Crisp file SVG icon
        item.innerHTML = `
            <svg class="explorer-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.split('/').pop()}</span>
        `;
        
        item.title = file; // Full path on hover
        
        item.addEventListener('click', async () => {
            if (!isSamePath(file, state.activeFile)) {
                const editorMod = await import('./editor.js');
                await editorMod.switchActiveFile(file);
            }
        });
        
        listContainer.appendChild(item);
    });
}
