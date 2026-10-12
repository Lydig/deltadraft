// desktop-app/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Copy suggestion text without exposing general clipboard access.
  copyRecommendations: (text) => ipcRenderer.invoke('copy-recommendations', text),

  // Release notices and a fixed download-page link.
  getUpdateState: () => ipcRenderer.invoke('updates:get-state'),
  checkForUpdates: () => ipcRenderer.invoke('updates:check'),
  openUpdateDownloads: () => ipcRenderer.invoke('updates:open-downloads'),
  onUpdateState: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on('updates:state', listener);
    return () => ipcRenderer.removeListener('updates:state', listener);
  },

  // Favorites
  getFavorites: () => ipcRenderer.invoke('get-favorites'),
  saveFavorites: (favorites) => ipcRenderer.invoke('save-favorites', favorites),
  
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // LCU
  getChampSelect: () => ipcRenderer.invoke('get-champ-select'),
  getPickableChampions: () => ipcRenderer.invoke('get-pickable-champions'),
});
