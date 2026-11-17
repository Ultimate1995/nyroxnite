// Läuft in jedem Tab. Nur interne Seiten (nyrox://) bekommen Zugriff auf Browser-Funktionen.
const { contextBridge, ipcRenderer } = require('electron');

if (location.protocol === 'nyrox:') {
  const stateListeners = [];
  ipcRenderer.on('page-state', (e, s) => stateListeners.forEach((fn) => fn(s)));
  contextBridge.exposeInMainWorld('nyrox', {
    state: () => ipcRenderer.invoke('page:state'),
    onState: (fn) => stateListeners.push(fn),
    history: (q) => ipcRenderer.invoke('page:history', q),
    deleteHistory: (i) => ipcRenderer.invoke('page:history-delete', i),
    clearData: (what) => ipcRenderer.invoke('page:clear-data', what),
    downloads: () => ipcRenderer.invoke('page:downloads'),
    downloadAct: (id, a) => ipcRenderer.invoke('page:download-act', id, a),
    set: (key, value) => ipcRenderer.invoke('page:set', key, value),
    pickFolder: () => ipcRenderer.invoke('page:pick-folder'),
    saveAccount: (data) => ipcRenderer.invoke('page:account-save', data),
    pickAvatar: () => ipcRenderer.invoke('page:account-avatar'),
    deleteAccount: () => ipcRenderer.invoke('page:account-delete'),
    open: (url, newTab) => ipcRenderer.send('page:open', url, newTab),
    act: (a) => ipcRenderer.send('page:act', a),
  });
}
