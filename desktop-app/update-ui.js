document.addEventListener('DOMContentLoaded', () => {
    const api = window.electronAPI;
    const version = document.getElementById('app-version');
    const preview = document.getElementById('update-preview-label');
    const message = document.getElementById('update-message');
    const action = document.getElementById('update-action');
    const downloads = document.getElementById('update-downloads');
    const progress = document.getElementById('update-progress');
    let state = null;
    let pending = false;
    let actionName = 'checkForUpdates';
    let localError = '';

    function render() {
        if (!state) {
            message.textContent = localError;
            downloads.hidden = !localError;
            return;
        }
        version.textContent = `v${state.currentVersion}`;
        preview.hidden = !state.preview;
        progress.hidden = state.status !== 'downloading';
        progress.value = state.progress;
        actionName = 'checkForUpdates';
        action.textContent = 'Check for updates';
        action.disabled = pending;
        action.classList.remove('update-ready');
        downloads.hidden = !['available', 'downloaded', 'error', 'disabled'].includes(state.status);
        let text = '';
        switch (state.status) {
            case 'disabled':
                text = state.message; action.disabled = true;
                break;
            case 'checking':
                text = 'Checking for updates…'; action.disabled = true;
                break;
            case 'up-to-date':
                text = 'You’re up to date.';
                break;
            case 'available':
                text = `Version ${state.version} is available.`;
                action.textContent = 'Download update'; actionName = 'downloadUpdate';
                action.classList.add('update-ready');
                break;
            case 'downloading':
                text = `Downloading version ${state.version} · ${state.progress}%`;
                action.textContent = 'Downloading…'; action.disabled = true;
                break;
            case 'downloaded':
            case 'confirming':
                text = state.liveTracking ? 'Update ready. Stop live tracking before restarting.' : `Version ${state.version} is ready to install.`;
                action.textContent = 'Restart and install'; actionName = 'installUpdate';
                action.classList.add('update-ready');
                action.disabled = pending || state.liveTracking || state.status === 'confirming';
                break;
            case 'installing':
                text = 'Starting the installer…'; action.textContent = 'Restarting…'; action.disabled = true;
                break;
            case 'preview-complete':
                text = state.message; action.textContent = 'Preview complete'; action.disabled = true;
                break;
            case 'error':
                text = state.message;
                action.textContent = 'Try again';
                actionName = { check: 'checkForUpdates', download: 'downloadUpdate', install: 'installUpdate' }[state.errorStage] || 'checkForUpdates';
                if (state.errorStage === 'install' && state.liveTracking) {
                    text = 'Stop live tracking before retrying the installer.';
                    action.disabled = true;
                }
                break;
        }
        message.textContent = localError || text;
    }

    function acceptState(next) {
        if (!next || (state && next.revision < state.revision)) return;
        state = next;
        localError = '';
        render();
    }

    action.addEventListener('click', async () => {
        if (pending || action.disabled) return;
        const method = actionName;
        pending = true;
        localError = '';
        render();
        try {
            acceptState(await api[method]());
        } catch (error) {
            console.warn('Update action failed:', error);
            localError = 'Could not complete that action. Please try again.';
        } finally {
            pending = false;
            render();
        }
    });
    downloads.addEventListener('click', async () => {
        try { await api.openUpdateDownloads(); }
        catch (error) {
            console.warn('Could not open update downloads:', error);
            localError = 'Could not open the download page. Please try again.';
            render();
        }
    });

    const unsubscribe = api.onUpdateState(acceptState);
    window.addEventListener('beforeunload', unsubscribe);
    // A renderer reload starts with tracking off, as does the existing draft UI.
    api.setUpdateLiveTracking(false).then(acceptState).catch(console.warn);
    api.getUpdateState().then(acceptState).catch(error => {
        console.warn('Could not read update status:', error);
        localError = 'Update status is unavailable. You can use the download page.';
        render();
    });
});
