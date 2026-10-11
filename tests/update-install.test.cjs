const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { once } = require('node:events');
const { prepareProject, NAME, PRODUCT, APP_ID, FEED, RUNTIME, MAIN_PREFIX } = require('./build-update-test.cjs');
const { createFeedServer } = require('./serve-update-test.cjs');

const repo = path.resolve(__dirname, '..');
const workspace = path.join(repo, 'workspace');

function temporaryDirectory(t) {
    fs.mkdirSync(workspace, { recursive: true });
    const directory = fs.mkdtempSync(path.join(workspace, 'update-test-check-'));
    t.after(() => {
        // All recursively removed paths are verified temporary children of workspace.
        const relative = path.relative(workspace, fs.realpathSync(directory));
        assert.ok(!path.isAbsolute(relative) && !relative.startsWith('..') && relative.startsWith('update-test-check-'));
        fs.rmSync(directory, { recursive: true });
    });
    return directory;
}

test('test builds isolate identity, settings, cache and feed while preserving production logic', t => {
    const directory = temporaryDirectory(t);
    const sourceFiles = [...RUNTIME, 'package.json', 'package-lock.json'];
    const originals = new Map(sourceFiles.map(file => [file, fs.readFileSync(path.join(repo, 'desktop-app', file), 'utf8')]));
    const project = prepareProject(path.join(directory, 'prepared'));
    const pkg = JSON.parse(fs.readFileSync(path.join(project, 'package.json'), 'utf8'));
    const original = JSON.parse(originals.get('package.json'));
    const lock = JSON.parse(fs.readFileSync(path.join(project, 'package-lock.json'), 'utf8'));
    assert.equal(pkg.name, NAME); assert.notEqual(pkg.name, original.name);
    assert.equal(pkg.productName, PRODUCT);
    assert.equal(pkg.build.appId, APP_ID); assert.notEqual(pkg.build.appId, original.build.appId);
    assert.equal(pkg.build.productName, PRODUCT);
    assert.equal(pkg.version, '0.0.1'); assert.equal(lock.version, pkg.version);
    assert.equal(lock.packages[''].name, pkg.name); assert.equal(lock.packages[''].version, pkg.version);
    assert.deepEqual(pkg.dependencies, original.dependencies);
    assert.deepEqual(pkg.devDependencies, original.devDependencies);
    assert.deepEqual(pkg.build.nsis, original.build.nsis);
    assert.deepEqual(pkg.build.files, original.build.files);
    assert.deepEqual(pkg.build.publish, { provider: 'generic', url: FEED, useMultipleRangeRequest: false });
    for (const file of ['preload.js', 'updater.js', 'update-ui.js']) {
        assert.equal(fs.readFileSync(path.join(project, file), 'utf8'), originals.get(file));
    }
    const main = fs.readFileSync(path.join(project, 'main.js'), 'utf8');
    assert.equal(main, MAIN_PREFIX + originals.get('main.js').replace("title: 'DraftDiff'", `title: '${PRODUCT}'`));
    assert.ok(main.indexOf("setPath('userData'") < main.indexOf('const userDataPath'), 'Isolation must happen before preferences paths are captured');
    assert.equal(fs.readFileSync(path.join(project, 'update-service.js'), 'utf8'), originals.get('update-service.js').replace('https://github.com/Lydig/deltadraft/releases/latest', FEED));
    assert.equal(fs.readFileSync(path.join(project, 'index.html'), 'utf8'), originals.get('index.html')
        .replace('<title>DraftDiff</title>', `<title>${PRODUCT}</title>`)
        .replace('                    DraftDiff', `                    ${PRODUCT}`));
    assert.ok(!fs.existsSync(path.join(project, 'update-preview.js')));
    for (const file of sourceFiles) assert.equal(fs.readFileSync(path.join(repo, 'desktop-app', file), 'utf8'), originals.get(file));
    assert.throws(() => prepareProject(path.join(directory, 'prepared')), /already exists/);
});

test('local feed serves only test artifacts and supports updater byte ranges', async t => {
    const directory = temporaryDirectory(t);
    const filename = 'DraftDiff-Update-Test-Setup-0.0.2.exe';
    fs.writeFileSync(path.join(directory, filename), '0123456789');
    fs.writeFileSync(path.join(directory, 'latest.yml'), 'version: 0.0.2\n');
    fs.writeFileSync(path.join(directory, 'private.txt'), 'must not be served');
    const server = createFeedServer(directory);
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    t.after(() => { server.closeAllConnections(); return new Promise(resolve => server.close(resolve)); });
    const base = `http://127.0.0.1:${server.address().port}`;
    assert.equal(server.address().address, '127.0.0.1');
    const latest = await fetch(`${base}/latest.yml?noCache=123`);
    assert.equal(latest.status, 200); assert.equal(await latest.text(), 'version: 0.0.2\n');
    const whole = await fetch(`${base}/${filename}`);
    assert.equal(whole.status, 200); assert.equal(await whole.text(), '0123456789');
    for (const [range, expected, header] of [
        ['bytes=2-5', '2345', 'bytes 2-5/10'], ['bytes=7-', '789', 'bytes 7-9/10'],
        ['bytes=-3', '789', 'bytes 7-9/10'], ['bytes=8-99', '89', 'bytes 8-9/10']
    ]) {
        const response = await fetch(`${base}/${filename}`, { headers: { Range: range } });
        assert.equal(response.status, 206); assert.equal(response.headers.get('content-range'), header);
        assert.equal(await response.text(), expected);
    }
    const head = await fetch(`${base}/${filename}`, { method: 'HEAD' });
    assert.equal(head.status, 200); assert.equal(head.headers.get('content-length'), '10'); assert.equal(await head.text(), '');
    for (const range of ['bytes=11-', 'bytes=6-2', 'bytes=-0', 'bytes=0-2,4-6', 'bytes=-']) {
        const response = await fetch(`${base}/${filename}`, { headers: { Range: range } });
        assert.equal(response.status, 416); assert.equal(response.headers.get('content-range'), 'bytes */10');
    }
    for (const location of ['/private.txt', '/%2e%2e%2fprivate.txt', '/install/anything.exe', '/DraftDiff-Setup-4.5.1.exe']) {
        assert.equal((await fetch(base + location)).status, 404);
    }
    assert.equal((await fetch(`${base}/latest.yml`, { method: 'POST' })).status, 405);
});
