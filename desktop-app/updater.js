const { EventEmitter } = require('node:events');

// Owns update state only. It never reads or changes draft data or LCU polling.
class UpdateController extends EventEmitter {
    constructor({ updater = null, currentVersion, preview = false, disabledReason = '', confirmInstall = async () => false, logger = console }) {
        super();
        this.updater = updater;
        this.confirmInstall = confirmInstall;
        this.logger = logger;
        this.operation = null;
        this.state = {
            revision: 0, status: updater ? 'idle' : 'disabled', currentVersion,
            version: null, progress: 0, errorStage: null, message: disabledReason,
            preview, liveTracking: false
        };
        if (!updater) return;

        // An app quit, including a Windows shutdown, must not install an update.
        updater.autoDownload = false;
        updater.autoInstallOnAppQuit = false;
        updater.autoRunAppAfterInstall = true;
        updater.allowPrerelease = false;
        updater.allowDowngrade = false;
        updater.disableWebInstaller = true;
        updater.on('update-available', info => this.publish({ status: 'available', version: info.version, progress: 0, message: '', errorStage: null }));
        updater.on('update-not-available', () => this.publish({ status: 'up-to-date', version: null, message: '', errorStage: null }));
        updater.on('download-progress', info => {
            if (this.state.status !== 'downloading' || !Number.isFinite(info.percent)) return;
            this.publish({ progress: Math.max(0, Math.min(100, Math.round(info.percent))) });
        });
        updater.on('update-downloaded', info => this.publish({ status: 'downloaded', version: info.version, progress: 100, message: '', errorStage: null }));
        updater.on('error', error => this.fail(error));
    }

    getState() { return { ...this.state }; }

    publish(change) {
        this.state = { ...this.state, ...change, revision: this.state.revision + 1 };
        this.emit('state', this.getState());
    }

    fail(error) {
        const stage = this.operation || (this.state.status === 'installing' ? 'install' : this.state.errorStage) || 'check';
        this.logger.warn('Desktop update failed:', error?.message || error);
        const messages = {
            check: 'Could not check for updates. Try again or open the download page.',
            download: 'The update could not be downloaded or verified. Try again or open the download page.',
            install: 'The installer could not be started. Try again or open the download page.'
        };
        this.publish({ status: 'error', errorStage: stage, message: messages[stage] });
    }

    setLiveTracking(active) {
        if (typeof active !== 'boolean') throw new TypeError('Expected a live-tracking flag');
        this.publish({ liveTracking: active });
        return this.getState();
    }

    async check() {
        if (!this.updater || this.operation || ['downloaded', 'installing', 'preview-complete'].includes(this.state.status) || this.state.errorStage === 'install') return this.getState();
        this.operation = 'check';
        this.publish({ status: 'checking', version: null, progress: 0, message: '', errorStage: null });
        try {
            const result = await this.updater.checkForUpdates();
            if (!result && this.state.status === 'checking') throw new Error('Update check unavailable');
        } catch (error) {
            this.fail(error);
        } finally {
            this.operation = null;
        }
        return this.getState();
    }

    async download() {
        const retry = this.state.status === 'error' && this.state.errorStage === 'download';
        if (!this.updater || this.operation || !(this.state.status === 'available' || retry)) return this.getState();
        this.operation = 'download';
        this.publish({ status: 'downloading', progress: 0, message: '', errorStage: null });
        try {
            await this.updater.downloadUpdate();
        } catch (error) {
            this.fail(error);
        } finally {
            this.operation = null;
        }
        return this.getState();
    }

    async install() {
        const retry = this.state.status === 'error' && this.state.errorStage === 'install';
        if (!this.updater || this.operation || this.state.liveTracking || !(this.state.status === 'downloaded' || retry)) return this.getState();
        this.operation = 'install';
        this.publish({ status: 'confirming', message: '', errorStage: null });
        try {
            const confirmed = await this.confirmInstall(this.getState());
            // Tracking can be enabled while a confirmation is open.
            if (!confirmed || this.state.liveTracking) {
                this.publish({ status: 'downloaded' });
            } else if (this.state.preview) {
                this.publish({ status: 'preview-complete', message: 'Preview complete. No installer was downloaded and the app has not restarted.' });
            } else {
                this.publish({ status: 'installing' });
                this.updater.quitAndInstall(true, true);
            }
        } catch (error) {
            this.fail(error);
        } finally {
            this.operation = null;
        }
        return this.getState();
    }
}

module.exports = { UpdateController };
