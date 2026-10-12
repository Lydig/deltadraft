const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');
const { UpdateNotice, startUpdateNotice, fetchLatestRelease, RELEASE_API, DOWNLOAD_URL } = require('../desktop-app/updates');
const appRoot = path.resolve(__dirname, '../desktop-app');
const release = tag_name => ({ tag_name, draft: false, prerelease: false });
const logger = { warn() {} };
const flush = () => new Promise(resolve => setImmediate(resolve));

test('release notices compare numeric versions and never suggest downgrades', async () => {
    for (const [currentVersion, tag, expected] of [
        ['4.9.10', 'v4.10.0', 'available'], ['4.5.1', 'v4.5.2', 'available'],
        ['4.5.1', '4.5.1', 'up-to-date'], ['4.6.0', 'v4.5.99', 'up-to-date'],
        ['5.0.0', 'v4.99.99', 'up-to-date']
    ]) {
        const notice = new UpdateNotice({ currentVersion, getRelease: async () => release(tag), logger });
        assert.equal((await notice.check()).status, expected);
    }
});

test('drafts, prereleases and malformed release responses are not offered', async () => {
    for (const result of [
        { ...release('v9.0.0'), draft: true }, { ...release('v9.0.0'), prerelease: true },
        release('v4.6.0-beta.1'), release('v04.6.0'), release('v4.6'),
        release('v99999999999999999999.0.0'), release('<script>'), null, { tag_name: 'v9.0.0' }
    ]) {
        const notice = new UpdateNotice({ currentVersion: '4.5.1', getRelease: async () => result, logger });
        const state = await notice.check();
        assert.equal(state.status, 'error'); assert.equal(state.version, null);
    }
});

test('network errors can retry and overlapping checks use one request', async () => {
    let fail = true, finish, calls = 0;
    const notice = new UpdateNotice({ currentVersion: '4.5.1', logger, getRelease: async () => {
        calls++;
        if (fail) throw new Error('Offline');
        return new Promise(resolve => { finish = resolve; });
    } });
    assert.equal((await notice.check()).status, 'error');
    fail = false;
    const checking = notice.check();
    assert.equal((await notice.check()).status, 'checking'); assert.equal(calls, 2);
    finish(release('v4.5.2')); await checking;
    assert.equal(notice.getState().status, 'available');
    const state = notice.getState(); state.status = 'corrupted';
    assert.equal(notice.getState().status, 'available');
});

test('release requests use the fixed public endpoint without credentials and handle HTTP failures', async () => {
    const response = await fetchLatestRelease(async (url, options) => {
        assert.equal(url, RELEASE_API);
        assert.equal(options.credentials, 'omit');
        assert.equal(options.headers.Authorization, undefined);
        assert.ok(options.signal instanceof AbortSignal);
        return { ok: true, json: async () => release('v4.5.2') };
    });
    assert.equal(response.tag_name, 'v4.5.2');
    for (const status of [404, 403, 500]) {
        await assert.rejects(fetchLatestRelease(async () => ({ ok: false, status })), new RegExp(String(status)));
    }
});

function serviceHarness(t, { packaged = false, preview = false } = {}) {
    const handlers = new Map(), opened = [], events = [], appEvents = {};
    let requests = 0;
    const frame = { url: pathToFileURL(path.join(appRoot, 'index.html')).href };
    const sender = { mainFrame: frame };
    const window = { isDestroyed: () => false, webContents: { send: (...args) => events.push(args) } };
    const notice = startUpdateNotice({
        app: { isPackaged: packaged, getVersion: () => '4.5.1', commandLine: { hasSwitch: () => preview, getSwitchValue: () => 'available' }, on: (event, callback) => { appEvents[event] = callback; } },
        ipcMain: { handle: (channel, callback) => handlers.set(channel, callback) },
        BrowserWindow: { getAllWindows: () => [window], fromWebContents: candidate => candidate === sender ? window : null },
        shell: { openExternal: async url => { opened.push(url); } },
        net: { fetch: async () => { requests++; return { ok: true, json: async () => release('v4.5.1') }; } }
    });
    t.after(() => appEvents['before-quit']());
    return { handlers, opened, events, notice, sender, frame, event: { sender, senderFrame: frame }, requests: () => requests };
}

test('IPC permits only the local main frame and exposes only checks and a fixed page link', async t => {
    const h = serviceHarness(t);
    assert.deepEqual([...h.handlers.keys()], ['updates:get-state', 'updates:check', 'updates:open-downloads']);
    await h.handlers.get('updates:check')(h.event);
    assert.equal(h.notice.getState().status, 'up-to-date'); assert.equal(h.requests(), 1);
    assert.ok(h.events.some(([channel, state]) => channel === 'updates:state' && state.status === 'up-to-date'));
    await h.handlers.get('updates:open-downloads')(h.event, 'https://untrusted.invalid');
    assert.deepEqual(h.opened, [DOWNLOAD_URL]);
    assert.throws(() => h.handlers.get('updates:check')({ sender: h.sender, senderFrame: { ...h.frame } }), /denied/);
    h.frame.url = 'https://untrusted.invalid';
    assert.throws(() => h.handlers.get('updates:open-downloads')(h.event), /denied/);
});

test('notice preview avoids network requests and cannot be enabled in a packaged app', async t => {
    const preview = serviceHarness(t, { preview: true });
    await preview.notice.check();
    assert.equal(preview.notice.getState().status, 'available'); assert.equal(preview.requests(), 0);
    const packaged = serviceHarness(t, { packaged: true, preview: true });
    await packaged.notice.check();
    assert.equal(packaged.notice.getState().preview, false); assert.equal(packaged.requests(), 1);
});

test('renderer checks via the version, offers only available updates and clears transient status', async () => {
    const elements = new Map(), handlers = {}, windowHandlers = {}, timers = new Map();
    let timerId = 0;
    for (const id of ['app-version', 'update-preview-label', 'update-message', 'update-downloads']) {
        elements.set(id, { textContent: '', hidden: false, disabled: false, events: {}, setAttribute() {}, addEventListener(event, fn) { this.events[event] = fn; } });
    }
    let listener, opened = 0;
    const current = { revision: 0, currentVersion: '4.5.1', preview: false, status: 'idle', version: null };
    const api = {
        getUpdateState: async () => current,
        onUpdateState: callback => { listener = callback; return () => {}; },
        checkForUpdates: async () => ({ ...current, revision: 2, status: 'available', version: '4.5.2' }),
        openUpdateDownloads: async () => { opened++; }
    };
    vm.runInNewContext(fs.readFileSync(path.join(appRoot, 'update-ui.js'), 'utf8'), {
        document: { getElementById: id => elements.get(id), addEventListener: (event, fn) => { handlers[event] = fn; } },
        window: { electronAPI: api, addEventListener: (event, fn) => { windowHandlers[event] = fn; } },
        setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
        clearTimeout: id => timers.delete(id)
    });
    handlers.DOMContentLoaded(); await flush();
    assert.equal(elements.get('update-downloads').hidden, true);
    assert.equal(elements.get('app-version').textContent, 'v4.5.1');
    await elements.get('app-version').events.click();
    assert.equal(elements.get('update-downloads').hidden, false);
    assert.match(elements.get('update-downloads').title, /4\.5\.2/);
    assert.equal(elements.get('update-message').textContent, '');
    assert.equal(opened, 0);
    listener({ ...current, revision: 1, status: 'up-to-date' });
    assert.equal(elements.get('update-downloads').hidden, false);
    await elements.get('update-downloads').events.click(); assert.equal(opened, 1);
    listener({ ...current, revision: 3, status: 'error' });
    assert.equal(elements.get('update-downloads').hidden, true);
    assert.equal(elements.get('app-version').disabled, false);
    assert.match(elements.get('update-message').textContent, /Could not check/);
    for (const timer of timers.values()) timer();
    timers.clear();
    assert.equal(elements.get('update-message').textContent, '');
    listener({ ...current, revision: 4, status: 'up-to-date' });
    assert.equal(elements.get('update-downloads').hidden, true);
    assert.match(elements.get('update-message').textContent, /up to date/);
    listener({ ...current, revision: 5, status: 'checking' });
    assert.equal(timers.size, 0); // A previous message must not clear an ongoing check.
    assert.equal(elements.get('app-version').disabled, true);
    listener({ ...current, revision: 6, status: 'up-to-date' });
    for (const timer of timers.values()) timer();
    assert.equal(elements.get('update-message').textContent, '');
    assert.equal(elements.get('app-version').disabled, false);
    windowHandlers.beforeunload();
    assert.equal(timers.size, 0);
});
