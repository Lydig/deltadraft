// desktop-app/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const https = require('https');
const fs = require('fs');

let win;

// --- START: LCU Credential Logic (adapted from reference repo) ---
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
    rejectUnauthorized: false, // Required for LCU's self-signed certificate
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
                        resolve(null); // Resolve with null if not in champ select (e.g., 404)
                    }
                });
            });
            req.on('error', (err) => reject(err));
        });
    } catch (error) {
        // This will catch errors from getLeagueCredentials (e.g., client not running)
        return null;
    }
}

// Register the IPC handler that our preload script will use
ipcMain.handle("get-champ-select", getChampSelect);
// --- END: LCU Credential Logic ---

function createWindow() {
    win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'), // Link our preload script
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