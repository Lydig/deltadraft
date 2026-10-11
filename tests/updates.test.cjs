const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');
const { UpdateController } = require('../desktop-app/updater');
const appRoot = path.resolve(__dirname, '../desktop-app');
const flush = () => new Promise(resolve => setImmediate(resolve));

class FakeUpdater extends EventEmitter {
    constructor() { super(); this.checks = 0; this.downloads = 0; this.installs = []; }
    async checkForUpdates() {
        this.checks++;
        this.emit('update-available', { version: '4.6.0' });
        return { updateInfo: { version: '4.6.0' } };
    }
    async downloadUpdate() {
        this.downloads++;
        this.emit('download-progress', { percent: 38.7 });
        this.emit('update-downloaded', { version: '4.6.0' });
        return ['unused-test-installer.exe'];
    }
    quitAndInstall(...args) { this.installs.push(args); }
}

function harness(options = {}) {
    const updater = new FakeUpdater();
    const controller = new UpdateController({ updater, currentVersion: '4.5.1', confirmInstall: async () => true, logger: { warn() {} }, ...options });
    return { updater, controller };
}

test('checks announce updates but never download or install automatically', async () => {
    const { updater, controller } = harness();
    assert.equal(updater.autoDownload, false);
    assert.equal(updater.autoInstallOnAppQuit, false);
    assert.equal(updater.allowPrerelease, false);
    assert.equal(updater.allowDowngrade, false);
    assert.equal(updater.disableWebInstaller, true);
    await controller.check();
    assert.equal(controller.getState().status, 'available');
    assert.equal(updater.downloads, 0);
    assert.equal(updater.installs.length, 0);
    await controller.install();
    assert.equal(updater.installs.length, 0);
    const snapshot = controller.getState(); snapshot.status = 'downloaded';
    assert.equal(controller.getState().status, 'available');
});

test('duplicate checks/downloads are ignored and a downloaded update survives periodic checks', async () => {
    const { updater, controller } = harness();
    let finish;
    updater.checkForUpdates = () => new Promise(resolve => { updater.checks++; finish = resolve; });
    const checking = controller.check();
    await controller.check(); await controller.download();
    assert.equal(updater.checks, 1); assert.equal(updater.downloads, 0);
    updater.emit('update-available', { version: '4.6.0' }); finish({}); await checking;
    updater.downloadUpdate = () => new Promise(resolve => { updater.downloads++; finish = resolve; });
    const downloading = controller.download();
    await controller.download(); await controller.check(); await controller.install();
    assert.equal(updater.downloads, 1); assert.equal(updater.checks, 1); assert.equal(updater.installs.length, 0);
    updater.emit('download-progress', { percent: 900 }); assert.equal(controller.getState().progress, 100);
    updater.emit('download-progress', { percent: NaN }); assert.equal(controller.getState().progress, 100);
    updater.emit('update-downloaded', { version: '4.6.0' }); finish([]); await downloading;
    await controller.check();
    assert.equal(updater.checks, 1); assert.equal(controller.getState().status, 'downloaded');
});

test('failed network checks can retry, and no-update is a distinct outcome', async () => {
    const { updater, controller } = harness();
    updater.checkForUpdates = async () => { throw new Error('network unavailable'); };
    await controller.check(); assert.equal(controller.getState().errorStage, 'check');
    updater.checkForUpdates = async () => { updater.emit('update-not-available', { version: '4.5.1' }); return {}; };
    await controller.check(); assert.equal(controller.getState().status, 'up-to-date');
});

test('a failed or unverified download cannot install, and retry remains a download', async () => {
    const { updater, controller } = harness();
    await controller.check();
    updater.downloadUpdate = async () => {
        const error = new Error('sha512 checksum mismatch');
        updater.emit('error', error); throw error;
    };
    await controller.download();
    assert.equal(controller.getState().status, 'error'); assert.equal(controller.getState().errorStage, 'download');
    await controller.install(); assert.equal(updater.installs.length, 0);
    updater.downloadUpdate = FakeUpdater.prototype.downloadUpdate;
    await controller.download(); assert.equal(controller.getState().status, 'downloaded');
});

test('restart requires a downloaded update and explicit confirmation; cancel keeps it ready', async () => {
    let confirmed = false;
    const { updater, controller } = harness({ confirmInstall: async () => confirmed });
    await controller.check(); await controller.download(); await controller.install();
    assert.equal(updater.installs.length, 0); assert.equal(controller.getState().status, 'downloaded');
    confirmed = true; await controller.install();
    assert.deepEqual(updater.installs, [[true, true]]);
    assert.equal(controller.getState().status, 'installing');
});

test('tracking blocks restart, including tracking enabled while confirmation is open', async () => {
    let confirmCalls = 0, confirm;
    const { updater, controller } = harness({ confirmInstall: () => new Promise(resolve => { confirmCalls++; confirm = resolve; }) });
    await controller.check(); await controller.download();
    controller.setLiveTracking(true); await controller.install(); assert.equal(confirmCalls, 0);
    controller.setLiveTracking(false);
    const installing = controller.install();
    await controller.install(); assert.equal(confirmCalls, 1);
    controller.setLiveTracking(true); confirm(true); await installing;
    assert.equal(updater.installs.length, 0); assert.equal(controller.getState().status, 'downloaded');
    assert.throws(() => controller.setLiveTracking('false'), /flag/);
});

test('asynchronous installer failure preserves the installer retry action', async () => {
    const { updater, controller } = harness();
    await controller.check(); await controller.download(); await controller.install();
    updater.emit('error', new Error('installer could not launch'));
    assert.equal(controller.getState().errorStage, 'install');
    await controller.check(); assert.equal(controller.getState().errorStage, 'install');
    await controller.install(); assert.equal(updater.installs.length, 2);
});

test('preview and unpackaged modes cannot invoke a real installer', async () => {
    const { updater, controller } = harness({ preview: true });
    await controller.check(); await controller.download(); await controller.install();
    assert.equal(controller.getState().status, 'preview-complete'); assert.equal(updater.installs.length, 0);
    const disabled = new UpdateController({ currentVersion: '4.5.1' });
    await disabled.check(); await disabled.download(); await disabled.install();
    assert.equal(disabled.getState().status, 'disabled');
});

function serviceHarness({ packaged = true, previewFlag = false } = {}) {
    const updater = new FakeUpdater(), handlers = new Map(), sent = [], opened = [], scheduled = [];
    let previewCreated = 0;
    const frame = { url: pathToFileURL(path.join(appRoot, 'index.html')).href };
    const sender = { mainFrame: frame };
    const window = { isDestroyed: () => false, webContents: { send: (...args) => sent.push(args) } };
    const source = fs.readFileSync(path.join(appRoot, 'update-service.js'), 'utf8');
    const context = {
        module: { exports: {} }, __dirname: appRoot, process: { platform: 'win32' },
        setTimeout: fn => { scheduled.push(fn); return { unref() {} }; },
        setInterval: fn => { scheduled.push(fn); return { unref() {} }; }, clearTimeout() {}, clearInterval() {},
        require(name) {
            if (name === './updater') return { UpdateController };
            if (name === 'electron-updater') return { autoUpdater: updater };
            if (name === './update-preview') return { PreviewUpdater: class extends FakeUpdater { constructor() { super(); previewCreated++; } } };
            return require(name);
        }
    };
    vm.runInNewContext(source, context);
    const controller = context.module.exports.startDesktopUpdates({
        app: { isPackaged: packaged, getVersion: () => '4.5.1', commandLine: { hasSwitch: () => previewFlag, getSwitchValue: () => '' }, on() {} },
        ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
        BrowserWindow: { getAllWindows: () => [window], fromWebContents: webContents => webContents === sender ? window : null },
        dialog: { showMessageBox: async () => ({ response: 1 }) }, shell: { openExternal: async url => opened.push(url) }
    });
    return { controller, updater, handlers, sent, opened, scheduled, previewCreated, event: { sender, senderFrame: frame } };
}

test('update IPC rejects remote pages and child frames, and the fallback URL is fixed', async () => {
    const h = serviceHarness();
    const open = h.handlers.get('updates:open-downloads');
    assert.throws(() => open({ ...h.event, senderFrame: { url: 'https://example.com' } }), /denied/);
    assert.throws(() => open({ ...h.event, senderFrame: { url: h.event.senderFrame.url } }), /denied/);
    await open(h.event, 'https://example.com/untrusted');
    assert.deepEqual(h.opened, ['https://github.com/Lydig/deltadraft/releases/latest']);
    await h.handlers.get('updates:check')(h.event);
    assert.equal(h.sent.at(-1)[0], 'updates:state');
    assert.equal(h.sent.at(-1)[1].status, 'available');
});

test('source launch has no update timers; packaged builds ignore the preview flag', async () => {
    const dev = serviceHarness({ packaged: false });
    assert.equal(dev.scheduled.length, 0); assert.equal(dev.controller.getState().status, 'disabled');
    const packaged = serviceHarness({ previewFlag: true });
    assert.equal(packaged.previewCreated, 0); assert.equal(packaged.controller.getState().preview, false);
    assert.equal(packaged.scheduled.length, 2);
    await packaged.scheduled[0](); assert.equal(packaged.updater.checks, 1); assert.equal(packaged.updater.downloads, 0);
    const preview = serviceHarness({ packaged: false, previewFlag: true });
    assert.equal(preview.previewCreated, 1); assert.equal(preview.controller.getState().preview, true);
});

test('renderer ignores stale snapshots and disables restart while tracking', async () => {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, { textContent: '', hidden: false, disabled: false, classList: { add() {}, remove() {} }, addEventListener(name, handler) { this[name] = handler; } });
        return elements.get(id);
    };
    let ready, listener, fetchState;
    const context = { console, document: { getElementById: element, addEventListener: (_, fn) => { ready = fn; } }, window: { addEventListener() {}, electronAPI: {
        onUpdateState: fn => { listener = fn; return () => {}; },
        setUpdateLiveTracking: async () => undefined,
        getUpdateState: () => new Promise(resolve => { fetchState = resolve; })
    } } };
    vm.runInNewContext(fs.readFileSync(path.join(appRoot, 'update-ui.js'), 'utf8'), context); ready();
    const downloaded = { revision: 4, status: 'downloaded', currentVersion: '4.5.1', version: '4.6.0', progress: 100, liveTracking: true };
    listener(downloaded);
    fetchState({ ...downloaded, revision: 1, status: 'idle', liveTracking: false }); await flush();
    assert.equal(element('update-action').textContent, 'Restart and install');
    assert.equal(element('update-action').disabled, true);
    listener({ ...downloaded, revision: 5, liveTracking: false });
    assert.equal(element('update-action').disabled, false);
    listener({ ...downloaded, revision: 6, status: 'error', errorStage: 'download', message: 'Download failed' });
    assert.equal(element('update-downloads').hidden, false);
    assert.equal(element('update-action').textContent, 'Try again');
});
