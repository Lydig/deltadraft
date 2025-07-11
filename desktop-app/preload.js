// desktop-app/preload.js
const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe, limited API to our renderer (index.html)
contextBridge.exposeInMainWorld('electronAPI', {
  // Expose the 'get-champ-select' function from our main.js
  getChampSelect: () => ipcRenderer.invoke('get-champ-select'),

  // --- NEW: Expose favorites functions ---
  getFavorites: () => ipcRenderer.invoke('get-favorites'),
  saveFavorites: (favorites) => ipcRenderer.invoke('save-favorites', favorites),
});