// desktop-app/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Favorites
  getFavorites: () => ipcRenderer.invoke('get-favorites'),
  saveFavorites: (favorites) => ipcRenderer.invoke('save-favorites', favorites),
  
  // --- NEW: Settings ---
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

  // LCU (Placeholder, not used but good to have)
  getChampSelect: () => ipcRenderer.invoke('get-champ-select'),
});