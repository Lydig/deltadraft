// Local-only feed for the isolated installation test. No npm dependencies.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { pipeline } = require('node:stream');

const PORT = 47831;
const ALLOWED = new Set([
    'latest.yml', 'DraftDiff-Update-Test-Setup-0.0.1.exe.blockmap',
    'DraftDiff-Update-Test-Setup-0.0.2.exe', 'DraftDiff-Update-Test-Setup-0.0.2.exe.blockmap'
]);

function createFeedServer(directory) {
    return http.createServer((request, response) => {
        if (!['GET', 'HEAD'].includes(request.method)) { response.writeHead(405).end(); return; }
        const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
        if (pathname === '/') {
            response.writeHead(200, { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' });
            response.end('DraftDiff Update Test feed. Follow README.md in the test kit. This is not a public release.');
            return;
        }
        const filename = pathname.slice(1);
        if (!ALLOWED.has(filename)) { response.writeHead(404).end(); return; }
        const file = path.join(directory, filename);
        let size;
        try { size = fs.statSync(file).size; } catch { response.writeHead(404).end(); return; }
        const headers = {
            'Content-Type': filename.endsWith('.yml') ? 'text/yaml' : 'application/octet-stream',
            'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes'
        };
        let start = 0, end = size - 1, status = 200;
        if (request.headers.range) {
            // The test's GenericProvider uses single byte-range requests.
            const match = /^bytes=(\d*)-(\d*)$/.exec(request.headers.range);
            if (!match || (!match[1] && !match[2])) { response.writeHead(416, { 'Content-Range': `bytes */${size}` }).end(); return; }
            if (match[1]) { start = Number(match[1]); end = match[2] ? Math.min(Number(match[2]), size - 1) : end; }
            else { start = Math.max(0, size - Number(match[2])); }
            if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= size) {
                response.writeHead(416, { 'Content-Range': `bytes */${size}` }).end(); return;
            }
            status = 206; headers['Content-Range'] = `bytes ${start}-${end}/${size}`;
        }
        headers['Content-Length'] = size === 0 ? 0 : end - start + 1;
        response.writeHead(status, headers);
        if (request.method === 'HEAD' || size === 0) { response.end(); return; }
        pipeline(fs.createReadStream(file, { start, end }), response, () => {});
    });
}

if (require.main === module) {
    const directory = path.resolve(process.argv[2] || path.join(__dirname, 'feed'));
    for (const filename of ALLOWED) {
        if (!fs.existsSync(path.join(directory, filename))) throw new Error(`Incomplete test kit: missing ${filename}`);
    }
    const server = createFeedServer(directory);
    server.on('error', error => {
        console.error(error.code === 'EADDRINUSE' ? `Port ${PORT} is already in use. Close the previous test feed before retrying.` : error.message);
        process.exitCode = 1;
    });
    server.listen(PORT, '127.0.0.1', () => {
        console.log(`DraftDiff Update Test feed: http://127.0.0.1:${PORT}/\nKeep this window open during the update test. Ctrl+C stops it.`);
    });
}

module.exports = { createFeedServer, PORT };
