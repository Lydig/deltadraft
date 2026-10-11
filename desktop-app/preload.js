// desktop-app/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Copy suggestion text without exposing general clipboard access.
  copyRecommendations: (text) => ipcRenderer.invoke('copy-recommendations', text),

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
