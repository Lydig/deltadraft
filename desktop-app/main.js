// desktop-app/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

// Define paths for storing user data
const userDataPath = app.getPath('userData');
const favoritesFilePath = path.join(userDataPath, 'favorites.json');
const settingsFilePath = path.join(userDataPath, 'settings.json');

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// --- IPC Handler for Favorites ---
ipcMain.handle('get-favorites', () => {
  try {
    if (fs.existsSync(favoritesFilePath)) {
      return JSON.parse(fs.readFileSync(favoritesFilePath, 'utf-8'));
    }
  } catch (error) {
    console.error('Failed to read favorites:', error);
  }
  return {}; // Return empty object if file doesn't exist or fails to parse
});

ipcMain.handle('save-favorites', (event, favorites) => {
  try {
    fs.writeFileSync(favoritesFilePath, JSON.stringify(favorites, null, 2));
  } catch (error) {
    console.error('Failed to save favorites:', error);
  }
});

// --- NEW: IPC Handlers for Settings ---
ipcMain.handle('get-settings', () => {
  try {
    if (fs.existsSync(settingsFilePath)) {
      return JSON.parse(fs.readFileSync(settingsFilePath, 'utf-8'));
    }
  } catch (error) {
    console.error('Failed to read settings:', error);
  }
  return {}; // Return empty object on failure
});

ipcMain.handle('save-settings', (event, settings) => {
  try {
    fs.writeFileSync(settingsFilePath, JSON.stringify(settings, null, 2));
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
});