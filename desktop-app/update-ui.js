document.addEventListener('DOMContentLoaded', () => {
    const api = window.electronAPI;
    const version = document.getElementById('app-version');
    const preview = document.getElementById('update-preview-label');
    const message = document.getElementById('update-message');
    const downloads = document.getElementById('update-downloads');
    let state = null, pending = false, messageTimer;

    function showStatus(text, temporary = true) {
        clearTimeout(messageTimer);
        message.textContent = text;
        if (text && temporary) messageTimer = setTimeout(() => { message.textContent = ''; }, 6000);
    }

    function render() {
        version.disabled = pending || state?.status === 'checking';
        version.textContent = state ? `v${state.currentVersion}` : 'Version';
        version.setAttribute('aria-label', state ? `Version ${state.currentVersion}. Check for updates` : 'Check for updates');
        downloads.hidden = state?.status !== 'available';
        downloads.title = state?.status === 'available' ? `Version ${state.version} is available. Open the download page` : 'Open the download page';
        if (state) {
            preview.hidden = !state.preview;
        }
    }

    function acceptState(next) {
        if (!next || (state && next.revision <= state.revision)) return;
        state = next;
        render();
        const messages = {
            checking: 'Checking for updates…',
            'up-to-date': 'You’re up to date.',
            error: 'Could not check for updates. Click the version to try again.'
        };
        showStatus(messages[state.status] || '', state.status !== 'checking');
    }

    version.addEventListener('click', async () => {
        if (version.disabled) return;
        pending = true;
        showStatus('Checking for updates…', false);
        render();
        try { acceptState(await api.checkForUpdates()); }
        catch { showStatus('Could not check for updates. Please try again.'); }
        finally { pending = false; render(); }
    });
    downloads.addEventListener('click', async () => {
        try { await api.openUpdateDownloads(); }
        catch { showStatus('Could not open the download page. Please try again.'); }
    });
    const unsubscribe = api.onUpdateState(acceptState);
    window.addEventListener('beforeunload', () => { clearTimeout(messageTimer); unsubscribe(); });
    api.getUpdateState().then(acceptState).catch(() => {
        if (!state) showStatus('Update status is unavailable. Click the version to try again.');
    });
    render();
});
