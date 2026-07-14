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
    graph3d: null,
    is3DActive: false,
    activeUpdateToast: null,
    updateToastCount: 0,
    updateToastTimer: null,
    isStabilizing: false,
    preStabilizationPhysicsState: false,

    // UI Workspace Layout state
    activeSidebarTab: 'explorer', // 'explorer' or 'analytics'
    isConsoleOpen: false,
    activeConsoleTab: 'health', // 'health', 'metadata', 'logs'
    selectedNode: null,
    logs: [] // holds SSE parse logs
};
