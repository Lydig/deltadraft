const { EventEmitter } = require('node:events');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const RELEASE_API = 'https://api.github.com/repos/Lydig/deltadraft/releases/latest';
const DOWNLOAD_URL = 'https://github.com/Lydig/deltadraft/releases/latest';

function stableVersion(value) {
    if (typeof value !== 'string' || !/^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(value)) return null;
    const version = value.replace(/^v/, '');
    return version.split('.').every(part => Number.isSafeInteger(Number(part))) ? version : null;
}

function isNewer(candidate, current) {
    const next = candidate.split('.').map(Number), installed = current.split('.').map(Number);
    for (let index = 0; index < 3; index++) {
        if (next[index] !== installed[index]) return next[index] > installed[index];
    }
    return false;
}

async function fetchLatestRelease(fetchImpl = globalThis.fetch) {
    const response = await fetchImpl(RELEASE_API, {
        headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'DraftDiff' },
        credentials: 'omit', cache: 'no-store', signal: AbortSignal.timeout(10000)
    });
    if (!response.ok) throw new Error(`GitHub returned ${response.status}`);
    return response.json();
}

// This controller only checks release information. It cannot download or install.
class UpdateNotice extends EventEmitter {
    constructor({ currentVersion, getRelease = fetchLatestRelease, preview = false, logger = console }) {
        super();
        this.getRelease = getRelease;
        this.logger = logger;
        this.checking = false;
        this.state = { revision: 0, currentVersion, preview, status: 'idle', version: null };
    }

    getState() { return { ...this.state }; }
    publish(change) {
        this.state = { ...this.state, ...change, revision: this.state.revision + 1 };
        this.emit('state', this.getState());
    }

    async check() {
        if (this.checking) return this.getState();
        this.checking = true;
        this.publish({ status: 'checking', version: null });
        try {
            const release = await this.getRelease();
            const version = stableVersion(release?.tag_name);
            const current = stableVersion(this.state.currentVersion);
            if (!version || !current || release.draft !== false || release.prerelease !== false) {
                throw new Error('Expected a published stable release');
            }
            this.publish({ status: isNewer(version, current) ? 'available' : 'up-to-date', version });
        } catch (error) {
            this.logger.warn('Could not check for a DraftDiff release:', error.message);
            this.publish({ status: 'error', version: null });
        } finally {
            this.checking = false;
        }
        return this.getState();
    }
}

function startUpdateNotice({ app, ipcMain, BrowserWindow, shell, net }) {
    const preview = !app.isPackaged && app.commandLine.hasSwitch('update-preview');
    const currentVersion = app.getVersion();
    const scenario = preview ? app.commandLine.getSwitchValue('update-preview') : '';
    const notice = new UpdateNotice({
        currentVersion, preview,
        getRelease: preview ? async () => {
            if (scenario === 'error') throw new Error('Preview: unavailable connection');
            const parts = currentVersion.split('.').map(Number);
            parts[2]++;
            return { tag_name: scenario === 'up-to-date' ? currentVersion : parts.join('.'), draft: false, prerelease: false };
        } : () => fetchLatestRelease(net.fetch.bind(net))
    });
    const rendererURL = pathToFileURL(path.join(__dirname, 'index.html')).href;
    const handle = (channel, action) => ipcMain.handle(channel, event => {
        if (event.senderFrame !== event.sender.mainFrame || event.senderFrame.url !== rendererURL || !BrowserWindow.fromWebContents(event.sender)) {
            throw new Error('Update request denied');
        }
        return action();
    });
    handle('updates:get-state', () => notice.getState());
    handle('updates:check', () => notice.check());
    // Never use a URL supplied by the renderer or by release metadata.
    handle('updates:open-downloads', () => shell.openExternal(DOWNLOAD_URL));
    notice.on('state', state => {
        for (const window of BrowserWindow.getAllWindows()) {
            if (!window.isDestroyed()) window.webContents.send('updates:state', state);
        }
    });
    const startup = setTimeout(() => notice.check(), preview ? 300 : 5000);
    startup.unref();
    app.on('before-quit', () => clearTimeout(startup));
    return notice;
}

module.exports = { UpdateNotice, startUpdateNotice, fetchLatestRelease, stableVersion, isNewer, RELEASE_API, DOWNLOAD_URL };
