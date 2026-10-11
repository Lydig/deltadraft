const { EventEmitter } = require('node:events');
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

// Used only in an unpackaged app with --update-preview. No network or installer.
class PreviewUpdater extends EventEmitter {
    constructor(currentVersion, scenario = 'available') {
        super();
        const [major, minor, patch] = currentVersion.split('.').map(Number);
        this.version = `${major}.${minor}.${patch + 1}`;
        this.scenario = scenario;
    }

    async checkForUpdates() {
        await pause(700);
        if (this.scenario === 'error') throw new Error('Simulated network failure');
        this.emit(this.scenario === 'up-to-date' ? 'update-not-available' : 'update-available', { version: this.version });
        return { updateInfo: { version: this.version } };
    }

    async downloadUpdate() {
        for (const percent of [8, 24, 48, 72, 100]) {
            await pause(500);
            if (percent === 48 && this.scenario === 'download-error') throw new Error('Simulated interrupted download');
            this.emit('download-progress', { percent });
        }
        this.emit('update-downloaded', { version: this.version });
        return [];
    }

    quitAndInstall() { throw new Error('Preview must never run an installer'); }
}

module.exports = { PreviewUpdater };
