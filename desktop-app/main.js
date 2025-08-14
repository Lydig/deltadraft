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