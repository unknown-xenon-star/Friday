import { state } from './state.js';
import { showToast, showBanner } from './ui.js';
import { updateGraphView } from './graph.js';

// Fetch source code and graph from disk
export async function syncWithDisk() {
    try {
        // Fetch code content for active file
        const fileRes = await fetch(`/api/file-content?file=${encodeURIComponent(state.activeFile)}`);
        const fileData = await fileRes.json();

        if (fileData.content !== undefined) {
            state.isCodeChangingProgrammatically = true;
            state.editor.setValue(fileData.content);
            state.isCodeChangingProgrammatically = false;
        }

        // Fetch and draw graph
        const graphRes = await fetch(`/api/graph`);
        const graphData = await graphRes.json();
        updateGraphView(graphData);
    } catch (err) {
        showBanner("Failed to sync code from disk: " + err.message, "error");
    }
}

// Parse code live using backend API
export async function parseCodeOnServer(code) {
    try {
        const response = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, filepath: state.activeFile })
        });
        const graphData = await response.json();
        updateGraphView(graphData);
    } catch (err) {
        console.error("Parsing error", err);
    }
}

// Dynamic file loader helper for switching workspace files in Monaco Editor
export async function switchActiveFile(filepath, targetLine = null) {
    try {
        const fileRes = await fetch(`/api/file-content?file=${encodeURIComponent(filepath)}`);
        const fileData = await fileRes.json();

        if (fileData.content !== undefined) {
            state.activeFile = filepath;
            document.getElementById('target-filename').textContent = filepath;

            state.isCodeChangingProgrammatically = true;
            state.editor.setValue(fileData.content);
            state.isCodeChangingProgrammatically = false;

            if (targetLine) {
                setTimeout(() => {
                    state.editor.revealLineInCenter(targetLine);
                    state.editor.setPosition({ lineNumber: targetLine, column: 1 });
                    state.editor.focus();
                    showToast(`📂 Opened <code>${filepath}</code> and jumped to line ${targetLine}`);
                }, 100);
            } else {
                showToast(`📂 Opened <code>${filepath}</code>`);
            }
        }
    } catch (err) {
        showBanner("Failed to switch active file: " + err.message, "error");
    }
}
