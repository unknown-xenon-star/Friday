export const state = {
    editor: null,
    network: null,
    nodesDataSet: new vis.DataSet(),
    edgesDataSet: new vis.DataSet(),
    config: { target_file: '', target_file_basename: '' },
    isCodeChangingProgrammatically: false,
    currentLayout: 'spring',
    isPhysicsEnabled: true,
    showExternalCalls: true,
    lastGraphData: null,
    activeFile: '',
    viewLevel: 'function',
    activeColorMode: 'standard',
    activeUpdateToast: null,
    updateToastCount: 0,
    updateToastTimer: null,
    isStabilizing: false,
    preStabilizationPhysicsState: false,

    // UI Workspace Layout state
    activeSidebarTab: 'explorer', // 'explorer' or 'analytics'
    isExplorerOpen: true,
    isConsoleOpen: false,
    activeConsoleTab: 'health', // 'health', 'metadata', 'logs'
    selectedNode: null,
    files: [],
    filteredFiles: [],
    logs: [] // holds SSE parse logs
};
