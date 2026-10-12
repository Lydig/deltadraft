// Run from the repository root: node --test tests/milestone1.test.cjs
// Executes each shipped inline script with a small DOM fixture; no network or League client required.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');

class Element {
    constructor() {
        this.dataset = {}; this.style = {}; this.children = []; this.value = ''; this.checked = false;
        this.hidden = false; this.textContent = ''; this.disabled = false;
        this.events = {}; this.attributes = {};
        const classes = new Set();
        this.classList = {
            contains: value => classes.has(value),
            add: (...values) => values.forEach(value => classes.add(value)),
            remove: (...values) => values.forEach(value => classes.delete(value)),
            toggle: (value, enabled = !classes.has(value)) => enabled ? classes.add(value) : classes.delete(value)
        };
    }
    set innerHTML(value) { this.html = value; this.children = []; }
    get innerHTML() { return this.html || ''; }
    addEventListener(event, callback) { this.events[event] = callback; }
    appendChild(child) { this.children.push(child); }
    querySelectorAll() { return this.children.filter(child => child.dataset.championName); }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    matches() { return false; }
}

function loadRenderer(app) {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    };
    const slots = ['left', 'right'].flatMap(side => ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'SUPPORT'].map(role => {
        const slot = new Element(); slot.dataset = { side, role }; return slot;
    }));
    const document = {
        body: element('body'), activeElement: null,
        getElementById: element,
        createElement: () => new Element(),
        querySelector: selector => element(selector),
        querySelectorAll: selector => selector === '#recommendation-list li' ? element('recommendation-list').children : selector === '.role-slot' ? slots : [],
        addEventListener: (event, callback) => { if (event === 'DOMContentLoaded') document.ready = callback; }
    };
    let copied = '', savedSettings;
    const context = vm.createContext({
        document, console, setTimeout: () => 1, clearTimeout() {},
        window: { addEventListener() {}, electronAPI: {
            copyRecommendations: async text => { copied = text; },
            saveSettings: async settings => { savedSettings = JSON.parse(JSON.stringify(settings)); }
        } },
        localStorage: { setItem(key, value) { if (key === 'draftdiff_settings') savedSettings = JSON.parse(value); } },
        navigator: { clipboard: { writeText: async text => { copied = text; } } },
        ResizeObserver: class { observe() {} }
    });
    let script = fs.readFileSync(path.join(root, app, 'index.html'), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
    script = script.replace('            initializeApp();', `
        globalThis.api = {
            getReferenceMatchup, updateCounterpickReference, displayFilteredRecommendations, applySettings,
            getCopyableRecommendations, copyRecommendations, updateCopyButton, updateAvailabilityUI,
            formatRecommendationShare, getRecommendations, getAnalysis, updateRecommendations,
            ${app === 'desktop-app' ? 'inferRoles, updateFromLiveGame,' : ''}
            setLoader(loader) { getDataset = loader; },
            setState(state) {
                allChampions = state.champions || [];
                recommendationTarget = state.target === undefined ? {side:'left', role:'MIDDLE'} : state.target;
                lastRecommendations = state.recommendations || [];
                unavailableChampions = new Set(state.unavailable || []);
                favorites = state.favorites || {};
                sortBy = state.sortBy || 'total_delta'; sortDirection = state.sortDirection || 'desc';
            },
            ${app === 'desktop-app' ? `prepareLive(session, probabilities, locks) {
                champIdToName = Object.fromEntries(allChampions.map(champ => [champ.key, champ.id]));
                roleProbabilities = probabilities; lockedSlots = new Map(locks);
                window.electronAPI.getChampSelect = async () => session;
                window.electronAPI.getPickableChampions = async () => [2, 3, 5];
                setChampionForSlot = (side, role, champ, hover) => {
                    const slot = document.querySelectorAll('.role-slot').find(s => s.dataset.side === side && s.dataset.role === role);
                    delete slot.dataset.champion; delete slot.dataset.hover;
                    if (champ) slot.dataset[hover ? 'hover' : 'champion'] = champ;
                };
                updateAnalysisView = async () => {}; updateRecommendations = async () => {};
            },` : ''}
            get helpText() { return helpText; }
        };
    `);
    vm.runInContext(script, context, { filename: `${app}/index.html` });
    document.ready();
    element('time-period-select').value = 'patch'; element('rank-select').value = 'platinum_plus';
    element('min-games-filter').value = '300';
    return { api: context.api, element, slots, copied: () => copied, savedSettings: () => savedSettings };
}

function dataset(sylas = 0.0966, malphite = -0.0964, games = 299) {
    return { matchup_stats: new Map([
        [JSON.stringify(['Sylas', 'MIDDLE', 'Malphite', 'MIDDLE', 'enemy']), { delta2: sylas, total_games: games }],
        [JSON.stringify(['Malphite', 'MIDDLE', 'Sylas', 'MIDDLE', 'enemy']), { delta2: malphite, total_games: 400 }]
    ]) };
}

const champion = (id, name = id, key = id) => ({ id, name, key, image: { full: `${id}.png` } });
const recommendation = (name, score, wr = 0.52, frequency = 0.8) => ({
    champion: name, total_delta: score, lane_delta: score, ally_delta: 0, enemy_delta: score,
    base_win_rate: wr, role_frequency: frequency, breakdown: []
});

for (const app of ['desktop-app', 'web-app']) {
    test(`${app}: reference starts collapsed and remembers expansion and collapse across reloads`, () => {
        let harness = loadRenderer(app);
        harness.api.applySettings({ minGames: '150' });
        assert.equal(harness.element('reference-values').hidden, true);
        harness.element('reference-toggle').events.click();
        assert.equal(harness.element('reference-values').hidden, false);
        assert.equal(harness.element('reference-toggle').attributes['aria-expanded'], 'true');
        const expanded = harness.savedSettings();
        assert.equal(expanded.minGames, '150');
        harness = loadRenderer(app);
        harness.api.applySettings(expanded);
        assert.equal(harness.element('reference-values').hidden, false);
        harness.element('reference-toggle').events.click();
        const collapsed = harness.savedSettings();
        harness = loadRenderer(app);
        harness.api.applySettings(collapsed);
        assert.equal(harness.element('reference-values').hidden, true);
        assert.equal(harness.element('reference-toggle').attributes['aria-expanded'], 'false');
    });

    test(`${app}: reference preserves both directions and flags samples without zeroing values`, () => {
        const { api } = loadRenderer(app);
        const forward = api.getReferenceMatchup(dataset(), 'Sylas', 'Malphite', 300);
        const reverse = api.getReferenceMatchup(dataset(), 'Malphite', 'Sylas', 300);
        assert.equal(forward.text, '+9.66'); assert.equal(forward.lowSample, true);
        assert.equal(reverse.text, '-9.64'); assert.equal(reverse.lowSample, false);
        assert.equal(api.getReferenceMatchup(dataset(0), 'Sylas', 'Malphite', 299).text, '+0.00');
        assert.equal(api.getReferenceMatchup(dataset(undefined, undefined, 300), 'Sylas', 'Malphite', 300).lowSample, false);
        assert.equal(api.getReferenceMatchup(null, 'Sylas', 'Malphite', 0).text, 'No data');
        assert.equal(api.getReferenceMatchup({matchup_stats: new Map()}, 'Sylas', 'Malphite', 0).text, 'No data');
        assert.equal(api.getReferenceMatchup(dataset(NaN), 'Sylas', 'Malphite', 0).text, 'No data');
    });

    test(`${app}: latest dataset wins even if a previous reference request finishes later`, async () => {
        const { api, element } = loadRenderer(app);
        const pending = [];
        api.setLoader(() => new Promise(resolve => pending.push(resolve)));
        const oldRequest = api.updateCounterpickReference();
        element('rank-select').value = 'diamond_plus'; element('time-period-select').value = '30';
        const newRequest = api.updateCounterpickReference();
        pending[1](dataset(0.12, -0.11)); await newRequest;
        pending[0](dataset(0.01, -0.02)); await oldRequest;
        assert.equal(element('reference-sylas').textContent, '+12.00');
        assert.equal(element('reference-malphite').textContent, '-11.00');
        assert.match(api.helpText.reference, /Last 30 Days · Diamond\+/);
        assert.match(api.helpText.reference, /299 games/);
        api.setLoader(async () => null); await api.updateCounterpickReference();
        assert.equal(element('reference-sylas').textContent, 'Unavailable');
        assert.equal(element('reference-sylas-warning').hidden, true);
    });

    test(`${app}: copied list respects filtering, favorites, displayed sort and availability`, async () => {
        const harness = loadRenderer(app); const { api, element } = harness;
        const champions = [champion('MonkeyKing', 'Wukong'), champion('Kaisa', "Kai'Sa"), champion('Ahri'), champion('Sylas'), champion('Malphite')];
        api.setState({ champions, recommendations: [
            recommendation('MonkeyKing', 4), recommendation('Kaisa', 3), recommendation('Ahri', 2),
            recommendation('Sylas', 5, 0.2), recommendation('Malphite', 6, 0.6, 0.01)
        ], favorites: {'MonkeyKing-MIDDLE': true, 'Kaisa-MIDDLE': true}, unavailable: ['Kaisa'], sortBy: 'champion', sortDirection: 'asc' });
        element('base-wr-filter').value = '45'; element('role-rate-filter').value = '5';
        element('favorites-only-toggle').checked = true;
        api.displayFilteredRecommendations();
        assert.equal(Array.from(api.getCopyableRecommendations()).join(','), 'Wukong');
        await api.copyRecommendations(); assert.equal(harness.copied(), 'MID recommendations based on current draft: Wukong');
        assert.equal(api.formatRecommendationShare('BOTTOM', ["Kai'Sa", 'Jinx']), "BOT recommendations based on current draft: Kai'Sa, Jinx");
        assert.equal(element('copy-status').textContent, 'Copied 1 champion');
        api.updateAvailabilityUI();
        assert.equal(element('copy-status').textContent, 'Copied 1 champion');
        element('favorites-only-toggle').checked = false;
        api.displayFilteredRecommendations();
        assert.equal(Array.from(api.getCopyableRecommendations()).join(','), 'Ahri,Wukong');
        element('recommendation-search').value = 'ahri'; api.displayFilteredRecommendations();
        assert.equal(Array.from(api.getCopyableRecommendations()).join(','), 'Ahri');
        element('recommendation-search').value = 'no-match'; api.displayFilteredRecommendations();
        assert.equal(element('copy-recommendations-btn').disabled, true);
    });

    test(`${app}: copy caps available results at ten and disables with no selected role`, async () => {
        const { api, element } = loadRenderer(app);
        const champions = Array.from({length: 14}, (_, i) => champion(`Champion${i}`));
        api.setState({champions, recommendations: champions.map((c, i) => recommendation(c.id, 14 - i)), unavailable: ['Champion0', 'Champion1']});
        api.displayFilteredRecommendations();
        assert.equal(Array.from(api.getCopyableRecommendations()).join(','), champions.slice(2, 12).map(c => c.name).join(','));
        api.setState({target: null}); await api.updateRecommendations();
        assert.equal(element('copy-recommendations-btn').disabled, true);
        assert.equal(api.getCopyableRecommendations().length, 0);
    });

    test(`${app}: a pending recommendation cannot refill the list after reset`, async () => {
        const { api, element } = loadRenderer(app);
        api.setState({});
        let resolve;
        api.setLoader(() => new Promise(done => { resolve = done; }));
        const pending = api.updateRecommendations();
        api.setState({target: null}); await api.updateRecommendations();
        resolve(dataset()); await pending;
        assert.equal(element('recommendation-list').innerHTML, '');
        assert.equal(element('copy-recommendations-btn').disabled, true);
    });
}

test('desktop: simulated live picks, hovers, bans and manual role locks still feed the draft', async () => {
    const { api, slots, element } = loadRenderer('desktop-app');
    const champions = [champion('Sylas', 'Sylas', '1'), champion('Ahri', 'Ahri', '2'), champion('Malphite', 'Malphite', '3'), champion('Zed', 'Zed', '4'), champion('Lux', 'Lux', '5')];
    api.setState({champions, target: null});
    const session = {
        actions: [[{type:'ban', completed:true, championId:4}]],
        myTeam: [{championId:1, championPickIntent:0}, {championId:0, championPickIntent:2}],
        theirTeam: [{championId:3, championPickIntent:0}]
    };
    api.prepareLive(session, {Sylas:{MIDDLE:0.9, TOP:0.1}, Ahri:{MIDDLE:1}, Malphite:{TOP:0.9, MIDDLE:0.1}}, [['left-TOP', 'Sylas']]);
    element('recommendation-list').children = champions.map(champ => {
        const row = new Element(); row.dataset.championName = champ.id; return row;
    });
    await api.updateFromLiveGame(true);
    const slot = (side, role) => slots.find(s => s.dataset.side === side && s.dataset.role === role).dataset;
    assert.equal(slot('left','TOP').champion, 'Sylas');
    assert.equal(slot('left','MIDDLE').hover, 'Ahri');
    assert.equal(slot('right','TOP').champion, 'Malphite');
    const rows = element('recommendation-list').children;
    assert.equal(rows.find(row => row.dataset.championName === 'Zed').classList.contains('unavailable'), true);
    assert.equal(rows.find(row => row.dataset.championName === 'Sylas').classList.contains('unavailable'), true);
    assert.equal(rows.find(row => row.dataset.championName === 'Lux').classList.contains('unavailable'), false);
});

test('desktop: preload routes recommendation copies through the native clipboard handler', async () => {
    const handlers = new Map();
    let exposed, copied;
    const electron = {
        app: { commandLine: { hasSwitch: () => false }, getPath: () => root, whenReady: () => ({ then() {} }), on() {} },
        ipcMain: { handle: (channel, handler) => handlers.set(channel, handler) },
        clipboard: { writeText: text => { copied = text; } },
        contextBridge: { exposeInMainWorld: (name, api) => { assert.equal(name, 'electronAPI'); exposed = api; } },
        ipcRenderer: { invoke: async (channel, ...args) => handlers.get(channel)({}, ...args) }
    };
    const mockRequire = name => name === 'electron' ? electron : require(name);
    for (const file of ['main.js', 'preload.js']) {
        vm.runInNewContext(fs.readFileSync(path.join(root, 'desktop-app', file), 'utf8'), { require: mockRequire }, { filename: file });
    }
    await exposed.copyRecommendations('MID: Sylas, Ahri');
    assert.equal(copied, 'MID: Sylas, Ahri');
    await assert.rejects(exposed.copyRecommendations({}), /Invalid recommendation text/);
    await assert.rejects(exposed.copyRecommendations('x'.repeat(2001)), /Invalid recommendation text/);
    assert.equal(copied, 'MID: Sylas, Ahri');
});
