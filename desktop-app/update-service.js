const { pathToFileURL } = require('node:url');
const path = require('node:path');
const { UpdateController } = require('./updater');

const DOWNLOAD_URL = 'https://github.com/Lydig/deltadraft/releases/latest';

function startDesktopUpdates({ app, ipcMain, BrowserWindow, dialog, shell, platform = process.platform }) {
    const preview = !app.isPackaged && app.commandLine.hasSwitch('update-preview');
    let updater = null;
    if (preview) {
        const { PreviewUpdater } = require('./update-preview');
        updater = new PreviewUpdater(app.getVersion(), app.commandLine.getSwitchValue('update-preview') || 'available');
    } else if (app.isPackaged && platform === 'win32') {
        updater = require('electron-updater').autoUpdater;
    }
    const controller = new UpdateController({
        updater, currentVersion: app.getVersion(), preview,
        disabledReason: !app.isPackaged ? 'Update checks are available in the installed desktop app.' : 'In-app updates are currently supported on Windows.',
        confirmInstall: async state => {
            const window = BrowserWindow.getAllWindows()[0];
            if (!window || window.isDestroyed()) return false;
            const { response } = await dialog.showMessageBox(window, {
                type: 'question', title: preview ? 'Preview update' : 'Install DraftDiff update',
                message: preview ? 'Simulate restarting to install the update?' : `Restart and install DraftDiff ${state.version}?`,
                detail: preview ? 'This preview will not download an installer, close the app, or change your installed version.' : 'Finish champion select before restarting. Your current draft will be cleared; saved settings and favorites will be kept.',
                buttons: [preview ? 'Simulate restart' : 'Restart and install', 'Cancel'],
                defaultId: 1, cancelId: 1, noLink: true
            });
            return response === 0;
        }
    });

    const rendererURL = pathToFileURL(path.join(__dirname, 'index.html')).href;
    const handle = (channel, action) => ipcMain.handle(channel, (event, ...args) => {
        // Only the local main frame may initiate downloads, restart, or open a URL.
        if (event.senderFrame !== event.sender.mainFrame || event.senderFrame.url !== rendererURL || !BrowserWindow.fromWebContents(event.sender)) {
            throw new Error('Update request denied');
        }
        return action(...args);
    });
    handle('updates:get-state', () => controller.getState());
    handle('updates:check', () => controller.check());
    handle('updates:download', () => controller.download());
    handle('updates:install', () => controller.install());
    handle('updates:set-live-tracking', active => controller.setLiveTracking(active));
    handle('updates:open-downloads', () => shell.openExternal(DOWNLOAD_URL));
    controller.on('state', state => {
        for (const window of BrowserWindow.getAllWindows()) {
            if (!window.isDestroyed()) window.webContents.send('updates:state', state);
        }
    });

    // Checking never downloads. Avoid interfering with app/data initialization.
    if (updater) {
        const startup = setTimeout(() => controller.check(), preview ? 300 : 5000);
        const periodic = setInterval(() => controller.check(), 6 * 60 * 60 * 1000);
        startup.unref(); periodic.unref();
        app.on('before-quit', () => { clearTimeout(startup); clearInterval(periodic); });
    }
    return controller;
}

module.exports = { startDesktopUpdates, DOWNLOAD_URL };
