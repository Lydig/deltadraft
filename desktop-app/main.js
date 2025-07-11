// desktop-app/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const https = require('https');
const fs = require('fs'); // --- NEW: Import File System module

let win;

// --- NEW: Path for storing favorites data ---
const favoritesPath = path.join(app.getPath('userData'), 'favorites.json');

// --- START: LCU Credential Logic ---
async function getLeagueCredentials() {
    return new Promise((resolve, reject) => {
        const command = 'wmic PROCESS WHERE name="LeagueClientUx.exe" GET commandline';
        exec(command, (error, stdout) => {
            if (error) {
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

async function getChampSelect() {
    try {
        const credentials = await getLeagueCredentials();
        const { port, password } = credentials;
        const auth = Buffer.from(`riot:${password}`).toString('base64');

        return new Promise((resolve, reject) => {
            const req = https.get({
                hostname: '127.0.0.1',
                port: port,
                path: '/lol-champ-select/v1/session',
                headers: { 'Authorization': `Basic ${auth}` },
                agent: httpsAgent
            }, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    if (res.statusCode === 200) {
                        resolve(JSON.parse(data));
                    } else {
                        resolve(null);
                    }
                });
            });
            req.on('error', (err) => reject(err));
        });
    } catch (error) {
        return null;
    }
}

ipcMain.handle("get-champ-select", getChampSelect);
// --- END: LCU Credential Logic ---


// --- NEW: IPC Handlers for Favorites ---
ipcMain.handle('get-favorites', async () => {
    try {
        if (fs.existsSync(favoritesPath)) {
            const data = fs.readFileSync(favoritesPath, 'utf-8');
            return JSON.parse(data);
        }
    } catch (error) {
        console.error('Failed to read favorites file:', error);
    }
    return {}; // Return empty object if file doesn't exist or fails to parse
});

ipcMain.handle('save-favorites', async (event, favorites) => {
    try {
        fs.writeFileSync(favoritesPath, JSON.stringify(favorites, null, 2));
    } catch (error) {
        console.error('Failed to save favorites file:', error);
    }
});
// --- END: IPC Handlers for Favorites ---


function createWindow() {
    win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    win.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});