// Read-only verification of a local Windows build: node tests/verify-update-package.cjs <output-directory>
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const asar = require('../desktop-app/node_modules/@electron/asar');
const yaml = require('../desktop-app/node_modules/js-yaml');

if (!process.argv[2]) throw new Error('Supply the local build output directory');
const output = path.resolve(process.argv[2]);
const resources = path.join(output, 'win-unpacked/resources');
const archive = path.join(resources, 'app.asar');
const files = asar.listPackage(archive).map(file => file.replaceAll('\\', '/'));
for (const required of ['/main.js', '/preload.js', '/updater.js', '/update-service.js', '/update-ui.js', '/node_modules/electron-updater/package.json']) {
    assert.ok(files.includes(required), `Missing runtime file: ${required}`);
}
assert.ok(!files.some(file => file.includes('update-preview.js') || file.startsWith('/dist/') || file.startsWith('/tests/')), 'Development files must not ship');
if (process.argv.includes('--runtime-only')) {
    console.log('Packaged runtime verified. Directory-only builds do not generate an update feed or installer; those checks remain pending.');
    process.exit(0);
}
const feed = yaml.load(fs.readFileSync(path.join(resources, 'app-update.yml'), 'utf8'));
assert.equal(feed.provider, 'github'); assert.equal(feed.owner, 'Lydig'); assert.equal(feed.repo, 'deltadraft');
const manifest = yaml.load(fs.readFileSync(path.join(output, 'latest.yml'), 'utf8'));
const pkg = JSON.parse(asar.extractFile(archive, 'package.json').toString());
assert.equal(manifest.version, pkg.version);
for (const artifact of manifest.files) {
    assert.equal(path.basename(artifact.url), artifact.url, 'Expected a local installer filename');
    const installer = fs.readFileSync(path.join(output, artifact.url));
    assert.equal(installer.length, artifact.size);
    assert.equal(crypto.createHash('sha512').update(installer).digest('base64'), artifact.sha512);
    assert.ok(fs.existsSync(path.join(output, `${artifact.url}.blockmap`)), 'Missing blockmap');
}
console.log('Update package verified: runtime, GitHub feed, version, filenames, sizes, SHA-512, and blockmap.');
