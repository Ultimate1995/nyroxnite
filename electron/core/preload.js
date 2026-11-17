// Brücke zwischen der Browser-Oberfläche (ui/index.html) und dem Hauptprozess
const { contextBridge, ipcRenderer } = require('electron');

const listeners = {};
for (const ch of ['state', 'tabs', 'banner', 'focus-url', 'find-open', 'find-result', 'hover-link', 'panel',
  'downloads', 'maximized', 'fullscreen', 'locked']) {
  ipcRenderer.on(ch, (e, data) => (listeners[ch] || []).forEach((fn) => fn(data)));
}

contextBridge.exposeInMainWorld('nyrox', {
  on: (ch, fn) => { (listeners[ch] = listeners[ch] || []).push(fn); },
  act: (action, arg) => ipcRenderer.send('ui:act', action, arg),
  activate: (id) => ipcRenderer.send('ui:activate', id),
  closeTab: (id) => ipcRenderer.send('ui:close-tab', id),
  moveTab: (id, to) => ipcRenderer.send('ui:move-tab', id, to),
  layout: (rect, panelRect) => ipcRenderer.send('ui:layout', rect, panelRect),
  open: (url, background) => ipcRenderer.send('ui:open', url, background),
  panel: (url) => ipcRenderer.send('ui:panel', url),
  panelAct: (a) => ipcRenderer.send('ui:panel-act', a),
  panelWidth: (px) => ipcRenderer.send('ui:panel-width', px),
  menu: (kind, arg, x, y) => ipcRenderer.send('ui:menu', kind, arg, x, y),
  windowAct: (a) => ipcRenderer.send('ui:window', a),
  suggest: (text) => ipcRenderer.invoke('ui:suggest', text),
  unlock: (pw) => ipcRenderer.invoke('ui:unlock', pw),
  addSite: () => ipcRenderer.send('ui:add-site'),
});
