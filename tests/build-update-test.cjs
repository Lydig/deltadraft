// Build two isolated Windows installations from the current desktop source.
// Run on an approved Windows build machine; this never publishes a release.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const REPO = path.resolve(__dirname, '..');
const APP = path.join(REPO, 'desktop-app');
const NAME = 'draftdiff-update-test';
const PRODUCT = 'DraftDiff Update Test';
const APP_ID = 'com.draftdiff.updatetest';
const FEED = 'http://127.0.0.1:47831/';
const VERSIONS = ['0.0.1', '0.0.2'];
const RUNTIME = ['index.html', 'main.js', 'preload.js', 'updater.js', 'update-service.js', 'update-ui.js'];
const MAIN_PREFIX = `// Generated test build: preferences are isolated from normal DraftDiff.\n{
    const { app: testApp } = require('electron');
    const testPath = require('node:path');
    testApp.setName('${PRODUCT}');
    testApp.setPath('userData', testPath.join(testApp.getPath('appData'), '${PRODUCT}'));
}\n`;

function replaceOnce(source, search, replacement) {
    assert.equal(source.split(search).length, 2, `Expected exactly one branding/configuration marker: ${search}`);
    return source.replace(search, replacement);
}

function prepareProject(output) {
    // Refuse to overwrite a previous run or any source directory.
    assert.ok(!fs.existsSync(output), `Output already exists; choose a new directory: ${output}`);
    fs.mkdirSync(output, { recursive: true });
    const project = path.join(output, 'app');
    fs.mkdirSync(project);
    const original = JSON.parse(fs.readFileSync(path.join(APP, 'package.json'), 'utf8'));
    const pkg = structuredClone(original);
    pkg.name = NAME;
    pkg.productName = PRODUCT;
    pkg.version = VERSIONS[0];
    pkg.description = 'Isolated DraftDiff installation test. Not a public release.';
    pkg.scripts = { dist: 'electron-builder --publish never' };
    pkg.build.appId = APP_ID;
    pkg.build.productName = PRODUCT;
    pkg.build.artifactName = 'DraftDiff-Update-Test-Setup-${version}.${ext}';
    pkg.build.publish = { provider: 'generic', url: FEED, useMultipleRangeRequest: false };
    // Keep the existing NSIS options, runtime and signature/checksum verification.
    fs.writeFileSync(path.join(project, 'package.json'), JSON.stringify(pkg, null, 2) + '\n');
    const lock = JSON.parse(fs.readFileSync(path.join(APP, 'package-lock.json'), 'utf8'));
    lock.name = NAME; lock.version = VERSIONS[0];
    lock.packages[''].name = NAME; lock.packages[''].version = VERSIONS[0];
    fs.writeFileSync(path.join(project, 'package-lock.json'), JSON.stringify(lock, null, 2) + '\n');
    for (const file of RUNTIME) {
        let source = fs.readFileSync(path.join(APP, file), 'utf8');
        if (file === 'main.js') {
            source = MAIN_PREFIX + replaceOnce(source, "title: 'DraftDiff'", `title: '${PRODUCT}'`);
        } else if (file === 'index.html') {
            source = replaceOnce(source, '<title>DraftDiff</title>', `<title>${PRODUCT}</title>`);
            source = replaceOnce(source, '                    DraftDiff', `                    ${PRODUCT}`);
        } else if (file === 'update-service.js') {
            source = replaceOnce(source, 'https://github.com/Lydig/deltadraft/releases/latest', FEED);
        }
        fs.writeFileSync(path.join(project, file), source);
    }
    for (const directory of ['assets', 'build']) {
        fs.cpSync(path.join(APP, directory), path.join(project, directory), { recursive: true });
    }
    return project;
}

function verifyBuild(output, version) {
    const asar = require('../desktop-app/node_modules/@electron/asar');
    const yaml = require('../desktop-app/node_modules/js-yaml');
    const crypto = require('node:crypto');
    const resources = path.join(output, 'win-unpacked', 'resources');
    const archive = path.join(resources, 'app.asar');
    const pkg = JSON.parse(asar.extractFile(archive, 'package.json').toString());
    assert.equal(pkg.name, NAME);
    assert.equal(pkg.productName, PRODUCT);
    assert.equal(pkg.version, version);
    const feed = yaml.load(fs.readFileSync(path.join(resources, 'app-update.yml'), 'utf8'));
    assert.equal(feed.provider, 'generic');
    assert.equal(feed.url, FEED);
    assert.equal(feed.useMultipleRangeRequest, false);
    assert.equal(feed.updaterCacheDirName, `${NAME}-updater`);
    const files = asar.listPackage(archive).map(file => file.replaceAll('\\', '/'));
    for (const file of RUNTIME) assert.ok(files.includes(`/${file}`), `Missing ${file}`);
    assert.ok(!files.includes('/update-preview.js'), 'Simulation must not ship in the install test');
    // The real updater, bridge and renderer must be exactly the production code.
    for (const file of ['updater.js', 'preload.js', 'update-ui.js']) {
        assert.equal(asar.extractFile(archive, file).toString(), fs.readFileSync(path.join(APP, file), 'utf8'));
    }
    assert.ok(asar.extractFile(archive, 'main.js').toString().startsWith(MAIN_PREFIX));
    const manifest = yaml.load(fs.readFileSync(path.join(output, 'latest.yml'), 'utf8'));
    assert.equal(manifest.version, version);
    const filename = `DraftDiff-Update-Test-Setup-${version}.exe`;
    assert.equal(manifest.path, filename);
    assert.equal(manifest.files.length, 1);
    assert.equal(manifest.files[0].url, filename);
    const installer = fs.readFileSync(path.join(output, filename));
    assert.equal(manifest.files[0].size, installer.length);
    const hash = crypto.createHash('sha512').update(installer).digest('base64');
    assert.equal(manifest.files[0].sha512, hash);
    assert.equal(manifest.sha512, hash);
    assert.ok(fs.statSync(path.join(output, `${filename}.blockmap`)).size > 0);
    return filename;
}

async function buildTest(output) {
    assert.equal(process.platform, 'win32', 'Use an approved Windows build machine');
    const project = prepareProject(output);
    // Use npm's JS entry point so paths with spaces do not require shell quoting.
    const npm = process.env.npm_execpath || path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js');
    assert.ok(fs.existsSync(npm), 'Cannot find npm next to Node.js');
    const install = spawnSync(process.execPath, [npm, 'ci', '--no-audit', '--no-fund'], { cwd: project, stdio: 'inherit' });
    if (install.error) throw install.error;
    assert.equal(install.status, 0, 'Test-project npm ci failed');
    const { build, Platform, Arch } = require('../desktop-app/node_modules/electron-builder');
    const outputs = [];
    for (const version of VERSIONS) {
        const destination = path.join(output, 'builds', version);
        await build({
            projectDir: project, targets: Platform.WINDOWS.createTarget('nsis', Arch.x64), publish: 'never',
            config: { extraMetadata: { version }, directories: { output: destination } }
        });
        outputs.push({ destination, filename: verifyBuild(destination, version) });
    }
    const kit = path.join(output, 'kit');
    fs.mkdirSync(path.join(kit, 'install'), { recursive: true });
    fs.mkdirSync(path.join(kit, 'feed'));
    fs.copyFileSync(path.join(outputs[0].destination, outputs[0].filename), path.join(kit, 'install', outputs[0].filename));
    for (const { destination, filename } of outputs) {
        fs.copyFileSync(path.join(destination, `${filename}.blockmap`), path.join(kit, 'feed', `${filename}.blockmap`));
    }
    for (const filename of [outputs[1].filename, 'latest.yml']) {
        fs.copyFileSync(path.join(outputs[1].destination, filename), path.join(kit, 'feed', filename));
    }
    fs.copyFileSync(path.join(__dirname, 'serve-update-test.cjs'), path.join(kit, 'start-feed.cjs'));
    fs.copyFileSync(path.join(REPO, 'docs', 'update-install-test.md'), path.join(kit, 'README.md'));
    console.log(`Verified test kit: ${kit}\nNo release was published. Install 0.0.1 and use its update button to reach 0.0.2.`);
}

if (require.main === module) {
    const args = process.argv.slice(2);
    const prepareOnly = args.includes('--prepare-only');
    const output = path.resolve(args.find(arg => !arg.startsWith('--')) || path.join(REPO, 'workspace', 'update-install-test'));
    const run = prepareOnly ? Promise.resolve().then(() => prepareProject(output)) : buildTest(output);
    run.then(result => { if (prepareOnly) console.log(`Prepared isolated source: ${result}`); })
        .catch(error => { console.error(error); process.exitCode = 1; });
}

module.exports = { prepareProject, verifyBuild, NAME, PRODUCT, APP_ID, FEED, VERSIONS, RUNTIME, MAIN_PREFIX };
