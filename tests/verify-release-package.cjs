// Verify the packaged app against the checkout used to build it; does not run the installer.
// Usage: node tests/verify-release-package.cjs workspace/release-candidate
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const asar = require('../desktop-app/node_modules/@electron/asar');

const root = path.resolve(__dirname, '..');
const output = process.argv[2];
assert.ok(output, 'Pass the build output directory');
const archive = path.resolve(root, output, 'win-unpacked/resources/app.asar');
const desktop = path.join(root, 'desktop-app');
const sourcePackage = JSON.parse(fs.readFileSync(path.join(desktop, 'package.json'), 'utf8'));
const packaged = JSON.parse(asar.extractFile(archive, 'package.json'));
assert.equal(packaged.version, sourcePackage.version);
assert.equal(packaged.name, sourcePackage.name);
assert.equal(packaged.license, sourcePackage.license);
assert.equal(packaged.main, 'main.js');
assert.equal(Object.keys(packaged.dependencies || {}).length, 0);

function verifyFile(source, relative) {
    assert.deepEqual(asar.extractFile(archive, path.normalize(relative)), fs.readFileSync(source), `Packaged file differs: ${relative}`);
}

for (const file of ['index.html', 'main.js', 'preload.js', 'updates.js', 'update-ui.js']) {
    verifyFile(path.join(desktop, file), file);
}
for (const file of ['LICENSE', 'THIRD_PARTY_NOTICES.md']) {
    verifyFile(path.join(root, file), file);
}

let assetCount = 0;
function verifyAssets(directory, relative = 'assets') {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const source = path.join(directory, entry.name);
        const target = `${relative}/${entry.name}`;
        if (entry.isDirectory()) verifyAssets(source, target);
        else if (entry.isFile()) { verifyFile(source, target); assetCount++; }
    }
}
verifyAssets(path.join(desktop, 'assets'));
const files = asar.listPackage(archive).map(file => file.replaceAll('\\', '/'));
assert.ok(!files.some(file => /\/(node_modules|tests|workspace|\.git)(\/|$)/.test(file)), 'Unexpected development files in the package');
console.log(`Verified DraftDiff ${packaged.version}: runtime source, licenses and ${assetCount} assets match the checkout.`);
