// desktop-app/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const https = require('https');

// Define paths for storing user data
const userDataPath = app.getPath('userData');
const favoritesFilePath = path.join(userDataPath, 'favorites.json');
const settingsFilePath = path.join(userDataPath, 'settings.json');
const windowStateFilePath = path.join(userDataPath, 'window-state.json'); // Added for saving window size/position

// --- START: LCU Credential & Champ Select Logic ---
async function getLeagueCredentials() {
    return new Promise((resolve, reject) => {
        const command = 'wmic PROCESS WHERE name="LeagueClientUx.exe" GET commandline';
        exec(command, (error, stdout) => {
            if (error || !stdout || stdout.includes('No Instance(s) Available.')) {
                return reject(new Error("League client process not found. Is the client running?"));
            }
            const portMatch = stdout.match(/--app-port=([0-9]+)/);
            const passwordMatch = stdout.match(/--remoting-auth-token=([\w-]+)/);

            if (portMatch && passwordMatch) {
                const port = portMatch[1];
                const password = passwordMatch[1];
                resolve({ port, password });
            } else {
                reject(new Error("Could not find port or password. Please ensure you are logged into the client."));
            }
        });
    });
}

const httpsAgent = new https.Agent({
    rejectUnauthorized: false,
});

async function lcuRequest(path) {
    try {
        const credentials = await getLeagueCredentials();
        const { port, password } = credentials;
        const auth = Buffer.from(`riot:${password}`).toString('base64');

        return new Promise((resolve, reject) => {
            const req = https.get({
                hostname: '127.0.0.1',
                port: port,
                path: path,
                headers: { 'Authorization': `Basic ${auth}` },
                agent: httpsAgent
            }, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    if (res.statusCode === 200) {
                        resolve(JSON.parse(data));
                    } else {
                        resolve(null); // Resolve with null for non-200 responses
                    }
                });
            });
            req.on('error', (err) => reject(err));
        });
    } catch (error) {
        return null;
    }
}

// --- IPC Handlers ---
ipcMain.handle("get-champ-select", () => lcuRequest('/lol-champ-select/v1/session'));
ipcMain.handle("get-pickable-champions", () => lcuRequest('/lol-champ-select/v1/pickable-champion-ids'));

ipcMain.handle('get-favorites', () => {
  try {
    if (fs.existsSync(favoritesFilePath)) {
      return JSON.parse(fs.readFileSync(favoritesFilePath, 'utf-8'));
    }
  } catch (error) {
    console.error('Failed to read favorites:', error);
  }
  return {};
});

ipcMain.handle('save-favorites', (event, favorites) => {
  try {
    fs.writeFileSync(favoritesFilePath, JSON.stringify(favorites, null, 2));
  } catch (error) {
    console.error('Failed to save favorites:', error);
  }
});

ipcMain.handle('get-settings', () => {
  try {
    if (fs.existsSync(settingsFilePath)) {
      return JSON.parse(fs.readFileSync(settingsFilePath, 'utf-8'));
    }
  } catch (error) {
    console.error('Failed to read settings:', error);
  }
  return {};
});

ipcMain.handle('save-settings', (event, settings) => {
  try {
    fs.writeFileSync(settingsFilePath, JSON.stringify(settings, null, 2));
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
});
// --- END: IPC Handlers ---


// --- Window State Logic ---
function getWindowState() {
  // Default values for first-time launch
  const defaultState = { width: 1280, height: 800, isMaximized: true };
  try {
    if (fs.existsSync(windowStateFilePath)) {
      const savedState = JSON.parse(fs.readFileSync(windowStateFilePath, 'utf-8'));
      return { ...defaultState, ...savedState };
    }
  } catch (error) {
    console.error('Failed to read window state:', error);
  }
  return defaultState;
}

function saveWindowState(window) {
  try {
    const isMaximized = window.isMaximized();
    // getNormalBounds saves the width/height the window falls back to when un-maximized
    const bounds = window.getNormalBounds(); 
    fs.writeFileSync(windowStateFilePath, JSON.stringify({ ...bounds, isMaximized }, null, 2));
  } catch (error) {
    console.error('Failed to save window state:', error);
  }
}
// --- END: Window State Logic ---


function createWindow() {
  const windowState = getWindowState();

  const mainWindow = new BrowserWindow({
    x: windowState.x,
    y: windowState.y,
    width: windowState.width,
    height: windowState.height,
    title: 'DraftDiff',
    icon: path.join(__dirname, 'assets/logo.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.setMenu(null);
  
  // If it was maximized when last closed (or if it's the first launch), maximize it now
  if (windowState.isMaximized) {
    mainWindow.maximize();
  }

  mainWindow.loadFile('index.html');

  // Set up listeners to save the window state when you move/resize/maximize it
  let saveTimeout;
  const debouncedSave = () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => saveWindowState(mainWindow), 500);
  };

  mainWindow.on('resize', debouncedSave);
  mainWindow.on('move', debouncedSave);
  mainWindow.on('maximize', debouncedSave);
  mainWindow.on('unmaximize', debouncedSave);
  
  // Also save reliably right before it closes
  mainWindow.on('close', () => saveWindowState(mainWindow));
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