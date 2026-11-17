// NyroxNite Browser by Tobias – Hauptprozess (Electron / castLabs mit Widevine)
'use strict';

const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const vm = require('vm');
const electron = require('electron');
const {
  app, BrowserWindow, WebContentsView, ipcMain, session, Menu, dialog, shell, protocol,
  nativeTheme, clipboard, nativeImage,
} = electron;

const CORE_DIR = process.env.NYROX_CORE_DIR || __dirname;
const CORE_KIND = process.env.NYROX_CORE_KIND || 'bundled';
const VERSION = JSON.parse(fs.readFileSync(path.join(CORE_DIR, 'version.json'), 'utf8')).version;
const APP_FULL = 'NyroxNite Browser by Tobias';
const UPDATE_BASE = 'https://raw.githubusercontent.com/Ultimate1995/nyroxnite/main/electron/core/';
const UPDATE_INTERVAL = 30 * 60 * 1000;

if (!process.env.NYROX_CORE_DIR) {
  app.setName('NyroxNite Browser');
  app.setPath('userData', path.join(app.getPath('appData'), 'NyroxNite Browser'));
}
const DATA = app.getPath('userData');
fs.mkdirSync(DATA, { recursive: true });
const CONFIG_FILE = path.join(DATA, 'config.json');
const AVATAR_FILE = path.join(DATA, 'avatar.png');
const LOG_FILE = path.join(DATA, 'fehler.log');

function log(msg) {
  try { fs.appendFileSync(LOG_FILE, `[${new Date().toLocaleString('de-DE')}] ${VERSION}: ${msg}\n`); } catch (e) { /* egal */ }
}
process.on('uncaughtException', (e) => log(e && e.stack ? e.stack : String(e)));
process.on('unhandledRejection', (e) => log('Promise: ' + (e && e.stack ? e.stack : String(e))));

// ====================================================================== Konfiguration
const SEARCH_ENGINES = {
  Google: 'https://www.google.com/search?q=',
  DuckDuckGo: 'https://duckduckgo.com/?q=',
  Bing: 'https://www.bing.com/search?q=',
  Ecosia: 'https://www.ecosia.org/search?q=',
  Startpage: 'https://www.startpage.com/do/search?q=',
};
const ACCENTS = {
  'Opera-Rot': ['#fa1e4e', '#ff5c7c'], Indigo: ['#6366f1', '#8b5cf6'], Blau: ['#2563eb', '#0ea5e9'],
  'Grün': ['#059669', '#14b8a6'], Rosa: ['#db2777', '#f472b6'], Orange: ['#ea580c', '#f59e0b'],
};
const DEFAULTS = {
  homepage: '', search_engine: 'Google', dark_mode: true, accent: 'Opera-Rot',
  adblock: true, block_popups: false, restore_session: true, show_bookmarks: true, show_sidebar: true,
  hardware_accel: true, sleep_tabs: true, ask_download: false,
  download_dir: path.join(app.getPath('home'), 'Downloads'),
  bookmarks: [
    { title: 'YouTube', url: 'https://www.youtube.com' },
    { title: 'Twitch', url: 'https://www.twitch.tv' },
    { title: 'Netflix', url: 'https://www.netflix.com' },
    { title: 'Wikipedia', url: 'https://de.wikipedia.org' },
  ],
  sidebar: [
    { title: 'WhatsApp', url: 'https://web.whatsapp.com' },
    { title: 'Discord', url: 'https://discord.com/app' },
    { title: 'Instagram', url: 'https://www.instagram.com' },
    { title: 'Spotify', url: 'https://open.spotify.com' },
    { title: 'YouTube', url: 'https://www.youtube.com' },
    { title: 'Twitch', url: 'https://www.twitch.tv' },
  ],
  panel_width: 420, history: [], session: [], zoom: {}, permissions: {}, account: null,
  last_version: '', running: false, imported: false,
};

let CFG = {};
function loadConfig() {
  CFG = JSON.parse(JSON.stringify(DEFAULTS));
  try {
    Object.assign(CFG, JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')));
  } catch (e) { /* neu */ }
  if (!CFG.imported) importOldConfig();
}
function importOldConfig() {
  // Daten aus der alten NyroxNite-Version (Python) übernehmen
  CFG.imported = true;
  const oldDir = path.join(app.getPath('appData'), 'NyroxNite');
  try {
    const old = JSON.parse(fs.readFileSync(path.join(oldDir, 'config.json'), 'utf8'));
    for (const k of ['homepage', 'search_engine', 'dark_mode', 'accent', 'adblock', 'block_popups',
      'restore_session', 'show_bookmarks', 'show_sidebar', 'sleep_tabs', 'bookmarks', 'sidebar', 'history',
      'zoom', 'account', 'panel_width']) {
      if (old[k] !== undefined && old[k] !== null) CFG[k] = old[k];
    }
    if (CFG.download_dir === undefined && old.download_dir) CFG.download_dir = old.download_dir;
    if (fs.existsSync(path.join(oldDir, 'avatar.png'))) fs.copyFileSync(path.join(oldDir, 'avatar.png'), AVATAR_FILE);
  } catch (e) { /* keine alte Version */ }
  saveConfig();
}
let saveTimer = null;
function saveConfig() {
  clearTimeout(saveTimer);
  saveTimer = null;
  CFG.history = (CFG.history || []).slice(-5000);
  try {
    const tmp = CONFIG_FILE + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(CFG));
    fs.renameSync(tmp, CONFIG_FILE);
  } catch (e) { log('Speichern: ' + e.message); }
}
function saveLater() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveConfig, 2500);
}
loadConfig();

if (!CFG.hardware_accel) app.disableHardwareAcceleration();
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

// Browser gibt sich als normales Chrome aus (sonst lehnen Netflix, WhatsApp & Co. ab)
const CHROME_VERSION = process.versions.chrome;
const USER_AGENT = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${CHROME_VERSION} Safari/537.36`;
app.userAgentFallback = USER_AGENT;

protocol.registerSchemesAsPrivileged([
  { scheme: 'nyrox', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } },
]);

// ====================================================================== Hilfsfunktionen
const PAGES = path.join(CORE_DIR, 'pages');
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json' };
const NEWTAB = 'nyrox://newtab/';
const isInternal = (u) => typeof u === 'string' && u.startsWith('nyrox://');
const isNewtab = (u) => typeof u === 'string' && u.startsWith('nyrox://newtab');

function theme() {
  const dark = !!CFG.dark_mode;
  const [a1, a2] = ACCENTS[CFG.accent] || ACCENTS['Opera-Rot'];
  return dark
    ? { dark, bg: '#0e0d13', surface: '#17161e', field: '#201f29', hover: '#272632', border: '#24232d', text: '#ecebf2', muted: '#8f8d9d', accent: a1, accent2: a2 }
    : { dark, bg: '#e9eaf0', surface: '#ffffff', field: '#f1f2f6', hover: '#e3e5ec', border: '#dfe1e8', text: '#1d2129', muted: '#6b7280', accent: a1, accent2: a2 };
}

function toUrl(text) {
  text = (text || '').trim();
  if (!text) return null;
  if (/^(https?|file|nyrox|view-source|about|chrome|data):/i.test(text)) return text;
  if (/^localhost(:\d+)?(\/.*)?$/i.test(text) || /^\d{1,3}(\.\d{1,3}){3}(:\d+)?(\/.*)?$/.test(text)) return 'http://' + text;
  if (!/\s/.test(text) && /^[^\s]+\.[a-z]{2,}(:\d+)?(\/.*)?$/i.test(text)) return 'https://' + text;
  return (SEARCH_ENGINES[CFG.search_engine] || SEARCH_ENGINES.Google) + encodeURIComponent(text);
}
function homeUrl() { return CFG.homepage && CFG.homepage.trim() ? toUrl(CFG.homepage) : NEWTAB; }
function hostOf(u) { try { return new URL(u).hostname; } catch (e) { return ''; } }
function versionTuple(v) { return String(v || '0').split('.').map((n) => parseInt(n, 10) || 0); }
function newer(a, b) {
  const x = versionTuple(a); const y = versionTuple(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  }
  return false;
}
function hashPw(pw, saltHex) {
  return crypto.pbkdf2Sync(pw, Buffer.from(saltHex, 'hex'), 200000, 32, 'sha256').toString('hex');
}
function avatarDataUrl() {
  try {
    if (CFG.account && CFG.account.avatar && fs.existsSync(AVATAR_FILE)) {
      return 'data:image/png;base64,' + fs.readFileSync(AVATAR_FILE).toString('base64');
    }
  } catch (e) { /* egal */ }
  return '';
}

// ====================================================================== Werbeblocker
const AD_HOSTS = new Set([
  'doubleclick.net', 'googlesyndication.com', 'googleadservices.com', 'adservice.google.com', 'ads.yahoo.com',
  'adnxs.com', 'taboola.com', 'outbrain.com', 'criteo.com', 'scorecardresearch.com', 'zedo.com', 'pubmatic.com',
  'rubiconproject.com', 'openx.net', 'moatads.com', 'amazon-adsystem.com', 'advertising.com', 'adform.net',
  'smartadserver.com', 'casalemedia.com', 'media.net', 'adsrvr.org', 'quantserve.com', 'yieldmo.com',
]);
function isAd(host) {
  if (!host) return false;
  const parts = host.split('.');
  for (let i = 0; i < parts.length - 1; i++) {
    if (AD_HOSTS.has(parts.slice(i).join('.'))) return true;
  }
  return false;
}

// ====================================================================== Sitzungen (Profile)
const preparedSessions = new WeakSet();
function prepareSession(ses) {
  if (preparedSessions.has(ses)) return ses;
  preparedSessions.add(ses);
  ses.setUserAgent(USER_AGENT);
  ses.protocol.handle('nyrox', (req) => {
    const u = new URL(req.url);
    let name = u.hostname || 'newtab';
    let rel = decodeURIComponent(u.pathname || '/').replace(/^\/+/, '');
    let file = rel ? path.join(PAGES, rel) : path.join(PAGES, name + '.html');
    if (!rel && !fs.existsSync(file)) file = path.join(PAGES, 'error.html');
    if (!path.resolve(file).startsWith(path.resolve(PAGES))) return new Response('Nein', { status: 403 });
    try {
      const body = fs.readFileSync(file);
      return new Response(body, { headers: { 'content-type': (MIME[path.extname(file)] || 'text/plain') + '; charset=utf-8' } });
    } catch (e) {
      return new Response('Nicht gefunden', { status: 404 });
    }
  });
  ses.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*'] }, (d, cb) => {
    if (CFG.adblock && d.resourceType !== 'mainFrame' && isAd(hostOf(d.url))) return cb({ cancel: true });
    cb({});
  });
  ses.setPermissionRequestHandler((wc, permission, callback, details) => {
    const auto = ['fullscreen', 'clipboard-sanitized-write', 'pointerLock', 'mediaKeySystem', 'window-management', 'speaker-selection'];
    if (auto.includes(permission)) return callback(true);
    const origin = (() => { try { return new URL(details.requestingUrl || wc.getURL()).origin; } catch (e) { return ''; } })();
    if (isInternal(origin)) return callback(true);
    const key = origin + '|' + permission;
    if (key in CFG.permissions) return callback(CFG.permissions[key]);
    const names = {
      media: 'Kamera/Mikrofon', geolocation: 'Standort', notifications: 'Benachrichtigungen', midi: 'MIDI-Geräte',
      'clipboard-read': 'Zwischenablage lesen', 'display-capture': 'Bildschirmfreigabe', openExternal: 'externe Programme öffnen',
    };
    const win = windowOfContents(wc);
    dialog.showMessageBox(win ? win.win : undefined, {
      type: 'question', buttons: ['Erlauben', 'Blockieren'], defaultId: 0, cancelId: 1,
      title: 'Berechtigung', message: `${hostOf(origin) || origin} möchte Zugriff auf: ${names[permission] || permission}`,
      checkboxLabel: 'Entscheidung merken', checkboxChecked: true,
    }).then((r) => {
      const ok = r.response === 0;
      if (r.checkboxChecked) { CFG.permissions[key] = ok; saveLater(); }
      callback(ok);
    }).catch(() => callback(false));
  });
  ses.on('will-download', (event, item, wc) => handleDownload(item, wc));
  return ses;
}

// ====================================================================== Downloads
const DOWNLOADS = [];
let dlCounter = 0;
function handleDownload(item, wc) {
  const id = ++dlCounter;
  const dir = CFG.download_dir || app.getPath('downloads');
  let target = path.join(dir, item.getFilename());
  if (CFG.ask_download) {
    const win = windowOfContents(wc);
    const p = dialog.showSaveDialogSync(win ? win.win : undefined, { defaultPath: target });
    if (!p) { item.cancel(); return; }
    target = p;
  } else {
    let n = 1;
    const ext = path.extname(target); const base = target.slice(0, -ext.length || undefined);
    while (fs.existsSync(target)) target = `${base} (${n++})${ext}`;
  }
  item.setSavePath(target);
  const d = { id, name: path.basename(target), path: target, url: item.getURL(), total: item.getTotalBytes(), received: 0, state: 'progressing', paused: false, started: Date.now() };
  DOWNLOADS.unshift(d);
  d.item = item;
  const push = () => broadcast('downloads', downloadsPublic());
  item.on('updated', (e, state) => { d.received = item.getReceivedBytes(); d.total = item.getTotalBytes(); d.state = state; d.paused = item.isPaused(); push(); });
  item.once('done', (e, state) => {
    d.state = state; d.received = item.getReceivedBytes(); d.item = null; push();
    if (state === 'completed') broadcastBanner(`Download fertig: ${d.name}`, 'Öffnen', 'open-download:' + id);
  });
  push();
  broadcastBanner(`Download gestartet: ${d.name}`);
}
function downloadsPublic() {
  return DOWNLOADS.slice(0, 100).map(({ item, ...d }) => d);
}

// ====================================================================== Fenster & Tabs
const WINDOWS = new Set();
let tabCounter = 0;

function windowOfContents(wc) {
  for (const w of WINDOWS) {
    if (w.win.webContents === wc) return w;
    for (const t of w.tabs) if (t.view && t.view.webContents === wc) return w;
    for (const p of w.panels.values()) if (p.webContents === wc) return w;
  }
  return null;
}
function broadcast(channel, data) {
  for (const w of WINDOWS) w.send(channel, data);
}
function broadcastBanner(text, button, action) {
  for (const w of WINDOWS) w.banner(text, button, action);
}

class NyroxWindow {
  constructor(opts = {}) {
    this.private = !!opts.private;
    this.ses = prepareSession(this.private
      ? session.fromPartition('nyrox-privat-' + Date.now())
      : session.defaultSession);
    this.tabs = [];
    this.active = null;
    this.closed = [];
    this.panels = new Map();
    this.panelUrl = null;
    this.contentRect = { x: 0, y: 120, width: 800, height: 600 };
    this.panelRect = null;
    this.locked = !!(CFG.account && CFG.account.pw) && opts.lock !== false;
    this.htmlFullscreen = false;
    const t = theme();
    this.win = new BrowserWindow({
      width: 1360, height: 880, minWidth: 640, minHeight: 420, show: false,
      backgroundColor: t.bg, titleBarStyle: 'hidden', title: APP_FULL,
      titleBarOverlay: { color: t.bg, symbolColor: t.text, height: 40 },
      icon: path.join(process.env.NYROX_BUNDLED_CORE || __dirname, '..', 'assets', 'icon.png'),
      webPreferences: { preload: path.join(CORE_DIR, 'preload.js'), contextIsolation: true, sandbox: false, spellcheck: false },
    });
    this.win.setMenuBarVisibility(false);
    this.win.loadFile(path.join(CORE_DIR, 'ui', 'index.html'));
    this.win.once('ready-to-show', () => this.win.show());
    this.win.on('closed', () => this.onClosed());
    this.win.on('close', () => saveSession());
    this.win.on('maximize', () => this.send('maximized', true));
    this.win.on('unmaximize', () => this.send('maximized', false));
    this.win.on('enter-full-screen', () => this.send('fullscreen', true));
    this.win.on('leave-full-screen', () => { this.htmlFullscreen = false; this.send('fullscreen', false); this.layout(); });
    this.win.webContents.on('before-input-event', (e, input) => this.onKey(e, input));
    this.win.webContents.on('did-finish-load', () => this.sendState());
    WINDOWS.add(this);
  }

  send(channel, data) {
    if (!this.win.isDestroyed()) this.win.webContents.send(channel, data);
  }

  banner(text, button, action) { this.send('banner', { text, button, action }); }

  sendState() {
    this.send('state', {
      version: VERSION, appName: APP_FULL, private: this.private, locked: this.locked,
      cfg: publicConfig(), theme: theme(), avatar: avatarDataUrl(),
      maximized: this.win.isMaximized(), downloads: downloadsPublic(), coreKind: CORE_KIND,
    });
    this.sendTabs();
  }

  sendTabs() {
    this.send('tabs', {
      active: this.active,
      tabs: this.tabs.map((t) => this.tabInfo(t)),
      panel: this.panelUrl,
    });
  }

  tabInfo(t) {
    const wc = t.view && !t.view.webContents.isDestroyed() ? t.view.webContents : null;
    const url = wc ? wc.getURL() || t.url : t.url;
    return {
      id: t.id, url: isNewtab(url) ? '' : (url.startsWith('nyrox://error') ? (new URL(url).searchParams.get('url') || url) : url), rawUrl: url, title: t.title || (isNewtab(url) ? 'Neuer Tab' : url),
      favicon: t.favicon || '', loading: !!t.loading, audible: wc ? wc.isCurrentlyAudible() : false,
      muted: wc ? wc.isAudioMuted() : false, canBack: wc ? wc.navigationHistory.canGoBack() : false,
      canForward: wc ? wc.navigationHistory.canGoForward() : false, discarded: !wc, pinned: !!t.pinned,
      zoom: wc ? Math.round(wc.getZoomFactor() * 100) : 100, crashed: !!t.crashed,
      bookmarked: CFG.bookmarks.some((b) => b.url === url),
    };
  }

  // ---------- Tabs
  createView(t, url) {
    const view = new WebContentsView({
      webPreferences: {
        session: this.ses, preload: path.join(CORE_DIR, 'page-preload.js'), contextIsolation: true,
        sandbox: true, spellcheck: true, backgroundThrottling: true,
      },
    });
    view.setBackgroundColor(theme().dark ? '#17161e' : '#ffffff');
    t.view = view;
    const wc = view.webContents;
    wc.setUserAgent(USER_AGENT);
    this.win.contentView.addChildView(view);
    view.setVisible(false);
    const upd = () => this.sendTabs();
    wc.on('page-title-updated', (e, title) => { t.title = title; upd(); this.updateTitle(); });
    wc.on('page-favicon-updated', (e, icons) => { t.favicon = icons && icons[0] ? icons[0] : ''; upd(); });
    wc.on('did-start-loading', () => { t.loading = true; t.crashed = false; upd(); });
    wc.on('did-stop-loading', () => { t.loading = false; upd(); this.addHistory(t); });
    wc.on('did-navigate', (e, u) => { t.url = u; t.favicon = isInternal(u) ? '' : t.favicon; this.applyZoom(t); upd(); saveSessionLater(); });
    wc.on('did-navigate-in-page', (e, u, main) => { if (main) { t.url = u; upd(); saveSessionLater(); } });
    wc.on('audio-state-changed', upd);
    wc.on('did-fail-load', (e, code, desc, failedUrl, isMain) => {
      if (!isMain || code === -3) return; // -3 = abgebrochen
      wc.loadURL(`nyrox://error/?code=${code}&desc=${encodeURIComponent(desc)}&url=${encodeURIComponent(failedUrl)}`);
    });
    wc.on('render-process-gone', (e, details) => {
      if (details.reason === 'clean-exit') return;
      t.crashed = true; upd();
      if (t.id === this.active) this.banner('Diese Seite ist abgestürzt.', 'Neu laden', 'reload-tab');
      log('Seite abgestürzt: ' + details.reason + ' ' + t.url);
    });
    wc.on('enter-html-full-screen', () => { this.htmlFullscreen = true; this.win.setFullScreen(true); this.layout(); });
    wc.on('leave-html-full-screen', () => { this.htmlFullscreen = false; this.win.setFullScreen(false); this.layout(); });
    wc.on('found-in-page', (e, r) => this.send('find-result', { active: r.activeMatchOrdinal, matches: r.matches }));
    wc.on('before-input-event', (e, input) => this.onKey(e, input));
    wc.on('update-target-url', (e, u) => this.send('hover-link', u));
    wc.on('context-menu', (e, params) => this.contextMenu(t, params));
    wc.setWindowOpenHandler(({ url, disposition }) => {
      if (disposition === 'new-window') {
        if (CFG.block_popups) { this.banner('Pop-up blockiert: ' + hostOf(url)); return { action: 'deny' }; }
        // echte Pop-ups (z. B. "Mit Google anmelden") als kleines Fenster öffnen, damit Logins funktionieren
        return { action: 'allow', overrideBrowserWindowOptions: { width: 520, height: 700, autoHideMenuBar: true, backgroundColor: theme().bg, title: APP_FULL } };
      }
      this.newTab(url, { background: disposition === 'background-tab', after: t.id });
      return { action: 'deny' };
    });
    wc.loadURL(url || t.url || NEWTAB);
    return view;
  }

  newTab(url, opts = {}) {
    const t = { id: ++tabCounter, url: url || NEWTAB, title: '', favicon: '', loading: true, lastActive: Date.now() };
    const idx = opts.after ? this.tabs.findIndex((x) => x.id === opts.after) + 1 : this.tabs.length;
    this.tabs.splice(idx > 0 ? idx : this.tabs.length, 0, t);
    if (!opts.lazy) this.createView(t, t.url);
    if (!opts.background || !this.active) this.activate(t.id);
    else this.sendTabs();
    if (!opts.background && isNewtab(t.url)) setTimeout(() => this.send('focus-url'), 80);
    return t;
  }

  tab(id) { return this.tabs.find((t) => t.id === id); }
  activeTab() { return this.tab(this.active); }

  activate(id) {
    const t = this.tab(id);
    if (!t) return;
    const prev = this.activeTab();
    if (prev && prev !== t) prev.lastActive = Date.now();
    this.active = id;
    t.lastActive = Date.now();
    if (!t.view || t.view.webContents.isDestroyed()) this.createView(t, t.url);
    for (const x of this.tabs) if (x.view && x !== t) x.view.setVisible(false);
    t.view.setVisible(!this.locked);
    this.layout();
    this.sendTabs();
    this.updateTitle();
    if (!isNewtab(t.url)) t.view.webContents.focus();
  }

  closeTab(id) {
    const i = this.tabs.findIndex((t) => t.id === id);
    if (i < 0) return;
    const t = this.tabs[i];
    if (!this.private && t.url && !isNewtab(t.url)) this.closed.push(t.url);
    this.destroyView(t);
    this.tabs.splice(i, 1);
    if (!this.tabs.length) { this.win.close(); return; }
    if (this.active === id) this.activate(this.tabs[Math.min(i, this.tabs.length - 1)].id);
    else this.sendTabs();
    saveSessionLater();
  }

  destroyView(t) {
    if (!t.view) return;
    try {
      this.win.contentView.removeChildView(t.view);
      if (!t.view.webContents.isDestroyed()) t.view.webContents.close();
    } catch (e) { /* egal */ }
    t.view = null;
  }

  moveTab(id, toIndex) {
    const i = this.tabs.findIndex((t) => t.id === id);
    if (i < 0) return;
    const [t] = this.tabs.splice(i, 1);
    this.tabs.splice(Math.max(0, Math.min(toIndex, this.tabs.length)), 0, t);
    this.sendTabs();
    saveSessionLater();
  }

  sleepTabs() {
    if (!CFG.sleep_tabs) return;
    const now = Date.now();
    for (const t of this.tabs) {
      if (t.id === this.active || !t.view || t.pinned) continue;
      const wc = t.view.webContents;
      if (wc.isDestroyed() || wc.isCurrentlyAudible() || wc.isDevToolsOpened()) continue;
      if (now - (t.lastActive || now) > 30 * 60 * 1000) { t.url = wc.getURL() || t.url; this.destroyView(t); }
    }
    this.sendTabs();
  }

  addHistory(t) {
    if (this.private || !t.view) return;
    const u = t.view.webContents.getURL();
    if (!/^https?:/.test(u)) return;
    const entry = { url: u, title: t.title || u, time: Date.now() };
    const last = CFG.history[CFG.history.length - 1];
    if (last && last.url === u) CFG.history[CFG.history.length - 1] = entry;
    else CFG.history.push(entry);
    saveLater();
  }

  applyZoom(t) {
    if (!t.view) return;
    const z = CFG.zoom[hostOf(t.url)];
    t.view.webContents.setZoomFactor(z || 1);
  }

  updateTitle() {
    const t = this.activeTab();
    if (t && !this.win.isDestroyed()) this.win.setTitle(`${t.title || 'Neuer Tab'} – ${APP_FULL}`);
  }

  // ---------- Layout (UI meldet, wo die Webseite hin soll)
  layout() {
    const t = this.activeTab();
    if (this.htmlFullscreen) {
      const [w, h] = this.win.getContentSize();
      if (t && t.view) t.view.setBounds({ x: 0, y: 0, width: w, height: h });
      for (const p of this.panels.values()) p.setVisible(false);
      return;
    }
    const r = this.contentRect;
    if (t && t.view) t.view.setBounds({ x: Math.round(r.x), y: Math.round(r.y), width: Math.max(0, Math.round(r.width)), height: Math.max(0, Math.round(r.height)) });
    for (const [url, p] of this.panels) {
      const show = url === this.panelUrl && this.panelRect && !this.locked;
      p.setVisible(!!show);
      if (show) {
        const pr = this.panelRect;
        p.setBounds({ x: Math.round(pr.x), y: Math.round(pr.y), width: Math.max(0, Math.round(pr.width)), height: Math.max(0, Math.round(pr.height)) });
      }
    }
  }

  // ---------- Seitenfenster (Seitenleiste)
  togglePanel(url) {
    if (this.panelUrl === url) { this.panelUrl = null; this.send('panel', null); this.layout(); this.sendTabs(); return; }
    if (!this.panels.has(url)) {
      const v = new WebContentsView({ webPreferences: { session: this.ses, sandbox: true, contextIsolation: true, backgroundThrottling: false } });
      v.setBackgroundColor(theme().dark ? '#17161e' : '#ffffff');
      v.webContents.setUserAgent(USER_AGENT);
      v.webContents.setWindowOpenHandler(({ url: u }) => { this.newTab(u); return { action: 'deny' }; });
      v.webContents.on('before-input-event', (e, input) => this.onKey(e, input));
      v.webContents.loadURL(url);
      this.win.contentView.addChildView(v);
      this.panels.set(url, v);
    }
    this.panelUrl = url;
    const item = CFG.sidebar.find((s) => s.url === url);
    this.send('panel', { url, title: item ? item.title : hostOf(url) });
    this.sendTabs();
  }

  panelAction(action) {
    const v = this.panels.get(this.panelUrl);
    if (!v) return;
    if (action === 'reload') v.webContents.reload();
    if (action === 'to-tab') { this.newTab(v.webContents.getURL()); this.togglePanel(this.panelUrl); }
  }

  removePanel(url) {
    const v = this.panels.get(url);
    if (v) { this.win.contentView.removeChildView(v); v.webContents.close(); this.panels.delete(url); }
    if (this.panelUrl === url) { this.panelUrl = null; this.send('panel', null); }
  }

  // ---------- Sperren
  setLocked(locked) {
    this.locked = locked;
    const t = this.activeTab();
    if (t && t.view) t.view.setVisible(!locked);
    this.layout();
    this.send('locked', locked);
  }

  // ---------- Kontextmenü der Webseite
  contextMenu(t, p) {
    const wc = t.view.webContents;
    const items = [];
    if (p.linkURL) {
      items.push(
        { label: 'Link in neuem Tab öffnen', click: () => this.newTab(p.linkURL, { background: true, after: t.id }) },
        { label: 'Link in privatem Fenster öffnen', click: () => createWindow({ private: true, urls: [p.linkURL] }) },
        { label: 'Link-Adresse kopieren', click: () => clipboard.writeText(p.linkURL) },
        { type: 'separator' },
      );
    }
    if (p.hasImageContents && p.srcURL) {
      items.push(
        { label: 'Bild in neuem Tab öffnen', click: () => this.newTab(p.srcURL, { background: true, after: t.id }) },
        { label: 'Bild speichern unter …', click: () => wc.downloadURL(p.srcURL) },
        { label: 'Bild kopieren', click: () => wc.copyImageAt(p.x, p.y) },
        { type: 'separator' },
      );
    }
    if (p.isEditable) {
      if (p.misspelledWord && p.dictionarySuggestions.length) {
        for (const s of p.dictionarySuggestions.slice(0, 4)) items.push({ label: s, click: () => wc.replaceMisspelling(s) });
        items.push({ type: 'separator' });
      }
      items.push({ label: 'Ausschneiden', role: 'cut' }, { label: 'Kopieren', role: 'copy' }, { label: 'Einfügen', role: 'paste' },
        { label: 'Alles auswählen', role: 'selectAll' }, { type: 'separator' });
    } else if (p.selectionText) {
      const sel = p.selectionText.trim().slice(0, 40);
      items.push({ label: 'Kopieren', role: 'copy' },
        { label: `Mit ${CFG.search_engine} nach „${sel}“ suchen`, click: () => this.newTab(toUrl(p.selectionText), { after: t.id }) },
        { type: 'separator' });
    }
    items.push(
      { label: 'Zurück', enabled: wc.navigationHistory.canGoBack(), click: () => wc.navigationHistory.goBack() },
      { label: 'Vor', enabled: wc.navigationHistory.canGoForward(), click: () => wc.navigationHistory.goForward() },
      { label: 'Neu laden', click: () => wc.reload() },
      { type: 'separator' },
      { label: 'Seite speichern unter …', click: () => this.act('save-page') },
      { label: 'Drucken …', click: () => wc.print() },
      { label: 'Seitenquelltext anzeigen', click: () => this.newTab('view-source:' + wc.getURL(), { after: t.id }) },
      { label: 'Untersuchen', click: () => wc.inspectElement(p.x, p.y) },
    );
    Menu.buildFromTemplate(items).popup({ window: this.win });
  }

  // ---------- Tastenkürzel (funktionieren auch, wenn die Webseite den Fokus hat)
  onKey(e, i) {
    if (i.type !== 'keyDown') return;
    const c = i.control || i.meta; const s = i.shift; const a = i.alt; const k = (i.key || '').toLowerCase();
    let action = null;
    if (c && !s && k === 't') action = 'new-tab';
    else if (c && s && k === 't') action = 'reopen-tab';
    else if (c && !s && k === 'w') action = 'close-tab';
    else if (c && !s && k === 'n') action = 'new-window';
    else if (c && s && k === 'n') action = 'new-private';
    else if ((c && k === 'l') || k === 'f6' || (a && k === 'd')) action = 'focus-url';
    else if (k === 'f5' || (c && !s && k === 'r')) action = c && k === 'f5' ? 'hard-reload' : 'reload';
    else if (c && s && k === 'r') action = 'hard-reload';
    else if (a && k === 'arrowleft') action = 'back';
    else if (a && k === 'arrowright') action = 'forward';
    else if (a && k === 'home') action = 'home';
    else if (c && k === 'tab') action = s ? 'prev-tab' : 'next-tab';
    else if (c && /^[1-9]$/.test(k)) action = 'tab-' + k;
    else if (c && !s && k === 'f') action = 'find';
    else if (c && !s && k === 'd') action = 'bookmark';
    else if (c && !s && k === 'h') action = 'history';
    else if (c && !s && k === 'j') action = 'downloads';
    else if (c && s && k === 'o') action = 'bookmarks';
    else if (c && s && k === 'b') action = 'toggle-bookmarks';
    else if (c && s && k === 's') action = 'toggle-sidebar';
    else if (c && (k === '+' || k === '=' || k === 'add')) action = 'zoom-in';
    else if (c && (k === '-' || k === 'subtract')) action = 'zoom-out';
    else if (c && k === '0') action = 'zoom-reset';
    else if (k === 'f11') action = 'fullscreen';
    else if (k === 'f12' || (c && s && k === 'i')) action = 'devtools';
    else if (c && !s && k === 'u') action = 'view-source';
    else if (c && !s && k === 'p') action = 'print';
    else if (c && s && k === 'p') action = 'save-pdf';
    else if (c && !s && k === 's') action = 'save-page';
    else if (c && k === ',') action = 'settings';
    else if (k === 'escape' && (this.win.isFullScreen())) action = 'exit-fullscreen';
    if (!action) return;
    if (this.locked && !['exit-fullscreen'].includes(action)) return;
    e.preventDefault();
    this.act(action);
  }

  // ---------- Aktionen aus Oberfläche, Menü und Tastatur
  act(action, arg) {
    const t = this.activeTab();
    const wc = t && t.view && !t.view.webContents.isDestroyed() ? t.view.webContents : null;
    switch (action) {
      case 'new-tab': return this.newTab(NEWTAB);
      case 'new-window': return createWindow();
      case 'new-private': return createWindow({ private: true });
      case 'close-tab': return t && this.closeTab(t.id);
      case 'reopen-tab': return this.closed.length && this.newTab(this.closed.pop());
      case 'focus-url': this.win.webContents.focus(); return this.send('focus-url');
      case 'navigate': { const u = toUrl(arg); if (u && t) { if (!wc) this.createView(t, u); else wc.loadURL(u); t.url = u; wc && wc.focus(); } return; }
      case 'back': return wc && wc.navigationHistory.canGoBack() && wc.navigationHistory.goBack();
      case 'forward': return wc && wc.navigationHistory.canGoForward() && wc.navigationHistory.goForward();
      case 'reload': return wc && wc.reload();
      case 'hard-reload': return wc && wc.reloadIgnoringCache();
      case 'stop': return wc && wc.stop();
      case 'reload-tab': if (t) { if (!wc) this.activate(t.id); else wc.reload(); } return;
      case 'home': return wc && wc.loadURL(homeUrl());
      case 'next-tab': case 'prev-tab': {
        if (!t) return;
        const i = this.tabs.indexOf(t); const n = this.tabs.length;
        return this.activate(this.tabs[(i + (action === 'next-tab' ? 1 : n - 1)) % n].id);
      }
      case 'find': this.win.webContents.focus(); return this.send('find-open');
      case 'find-text': if (wc) { if (arg && arg.text) wc.findInPage(arg.text, { forward: !arg.back, findNext: !!arg.next, matchCase: !!arg.matchCase }); else wc.stopFindInPage('clearSelection'); } return;
      case 'find-close': return wc && wc.stopFindInPage('clearSelection');
      case 'bookmark': return this.toggleBookmark();
      case 'history': return this.openInternal('history');
      case 'downloads': return this.openInternal('downloads');
      case 'bookmarks': return this.openInternal('bookmarks');
      case 'settings': return this.openInternal('settings');
      case 'about': return this.openInternal('about');
      case 'toggle-bookmarks': CFG.show_bookmarks = !CFG.show_bookmarks; saveLater(); return broadcastState();
      case 'toggle-sidebar': CFG.show_sidebar = !CFG.show_sidebar; saveLater(); if (!CFG.show_sidebar) for (const w of WINDOWS) { w.panelUrl = null; w.send('panel', null); } return broadcastState();
      case 'zoom-in': case 'zoom-out': case 'zoom-reset': {
        if (!wc) return;
        let f = action === 'zoom-reset' ? 1 : Math.round((wc.getZoomFactor() + (action === 'zoom-in' ? 0.1 : -0.1)) * 100) / 100;
        f = Math.max(0.25, Math.min(5, f));
        wc.setZoomFactor(f);
        const h = hostOf(wc.getURL());
        if (h && !this.private) { if (f === 1) delete CFG.zoom[h]; else CFG.zoom[h] = f; saveLater(); }
        return this.sendTabs();
      }
      case 'fullscreen': return this.win.setFullScreen(!this.win.isFullScreen());
      case 'exit-fullscreen': if (wc && this.htmlFullscreen) wc.executeJavaScript('document.exitFullscreen && document.exitFullscreen()').catch(() => {}); return this.win.setFullScreen(false);
      case 'devtools': return wc && (wc.isDevToolsOpened() ? wc.closeDevTools() : wc.openDevTools({ mode: 'detach' }));
      case 'view-source': return wc && this.newTab('view-source:' + wc.getURL(), { after: t.id });
      case 'print': return wc && wc.print();
      case 'save-pdf': return wc && this.savePdf(wc, t);
      case 'save-page': return wc && this.savePage(wc, t);
      case 'mute': { const x = this.tab(arg) || t; if (x && x.view) x.view.webContents.setAudioMuted(!x.view.webContents.isAudioMuted()); return this.sendTabs(); }
      case 'pin': { const x = this.tab(arg); if (x) { x.pinned = !x.pinned; this.tabs.sort((p, q) => (q.pinned ? 1 : 0) - (p.pinned ? 1 : 0)); } return this.sendTabs(); }
      case 'duplicate': { const x = this.tab(arg); return x && this.newTab(x.url, { after: x.id }); }
      case 'close-others': for (const x of this.tabs.slice()) if (x.id !== arg && !x.pinned) this.closeTab(x.id); return;
      case 'close-right': { const i = this.tabs.findIndex((x) => x.id === arg); for (const x of this.tabs.slice(i + 1)) this.closeTab(x.id); return; }
      case 'theme': CFG.dark_mode = !CFG.dark_mode; saveLater(); return broadcastState();
      case 'adblock': CFG.adblock = !CFG.adblock; saveLater(); broadcastState(); return this.banner(CFG.adblock ? 'Werbeblocker eingeschaltet' : 'Werbeblocker ausgeschaltet');
      case 'lock': return lockAll();
      case 'restart': return restartApp();
      case 'check-update': return checkOnlineUpdate(true);
      case 'quit': return app.quit();
      default:
        if (/^tab-\d$/.test(action)) {
          const n = parseInt(action.slice(4), 10);
          const target = n === 9 ? this.tabs[this.tabs.length - 1] : this.tabs[n - 1];
          return target && this.activate(target.id);
        }
        if (action.startsWith('open-path:')) return shell.openPath(action.slice('open-path:'.length));
        if (action.startsWith('open-download:')) {
          const d = DOWNLOADS.find((x) => x.id === parseInt(action.split(':')[1], 10));
          return d && shell.openPath(d.path);
        }
    }
    return undefined;
  }

  openInternal(name) {
    const [base, hash] = name.split('#');
    const prefix = `nyrox://${base}/`;
    const url = prefix + (hash ? '#' + hash : '');
    const existing = this.tabs.find((x) => (x.url || '').startsWith(prefix));
    if (existing) {
      if (hash && existing.view) existing.view.webContents.loadURL(url);
      return this.activate(existing.id);
    }
    const t = this.activeTab();
    if (t && isNewtab(t.url) && t.view) { t.view.webContents.loadURL(url); return t; }
    return this.newTab(url);
  }

  toggleBookmark() {
    const t = this.activeTab();
    if (!t || !t.view) return;
    const u = t.view.webContents.getURL();
    if (!u || isInternal(u)) return;
    const i = CFG.bookmarks.findIndex((b) => b.url === u);
    if (i >= 0) { CFG.bookmarks.splice(i, 1); this.banner('Lesezeichen entfernt'); }
    else { CFG.bookmarks.push({ title: t.title || hostOf(u), url: u }); this.banner('Lesezeichen gespeichert'); }
    saveLater();
    broadcastState();
  }

  async savePdf(wc, t) {
    const r = await dialog.showSaveDialog(this.win, { defaultPath: path.join(CFG.download_dir, safeName(t.title) + '.pdf'), filters: [{ name: 'PDF', extensions: ['pdf'] }] });
    if (r.canceled || !r.filePath) return;
    const data = await wc.printToPDF({ printBackground: true });
    fs.writeFileSync(r.filePath, data);
    this.banner('PDF gespeichert', 'Öffnen', 'open-path:' + r.filePath);
  }

  async savePage(wc, t) {
    const r = await dialog.showSaveDialog(this.win, { defaultPath: path.join(CFG.download_dir, safeName(t.title) + '.html'), filters: [{ name: 'Webseite, komplett', extensions: ['html'] }, { name: 'Webarchiv', extensions: ['mhtml'] }] });
    if (r.canceled || !r.filePath) return;
    await wc.savePage(r.filePath, r.filePath.endsWith('.mhtml') ? 'MHTML' : 'HTMLComplete');
    this.banner('Seite gespeichert');
  }

  showMainMenu(x, y) {
    const tpl = [
      { label: 'Neuer Tab', accelerator: 'Ctrl+T', click: () => this.act('new-tab') },
      { label: 'Neues Fenster', accelerator: 'Ctrl+N', click: () => this.act('new-window') },
      { label: 'Neues privates Fenster', accelerator: 'Ctrl+Shift+N', click: () => this.act('new-private') },
      { type: 'separator' },
      { label: 'Verlauf', accelerator: 'Ctrl+H', click: () => this.act('history') },
      { label: 'Lesezeichen', accelerator: 'Ctrl+Shift+O', click: () => this.act('bookmarks') },
      { label: 'Downloads', accelerator: 'Ctrl+J', click: () => this.act('downloads') },
      { label: 'Geschlossenen Tab wiederherstellen', accelerator: 'Ctrl+Shift+T', click: () => this.act('reopen-tab') },
      { type: 'separator' },
      { label: 'Lesezeichenleiste', type: 'checkbox', checked: !!CFG.show_bookmarks, accelerator: 'Ctrl+Shift+B', click: () => this.act('toggle-bookmarks') },
      { label: 'Seitenleiste', type: 'checkbox', checked: !!CFG.show_sidebar, accelerator: 'Ctrl+Shift+S', click: () => this.act('toggle-sidebar') },
      { label: 'Zoom', submenu: [
        { label: 'Vergrößern', accelerator: 'Ctrl+Plus', click: () => this.act('zoom-in') },
        { label: 'Verkleinern', accelerator: 'Ctrl+-', click: () => this.act('zoom-out') },
        { label: 'Zurücksetzen', accelerator: 'Ctrl+0', click: () => this.act('zoom-reset') },
      ] },
      { label: 'Vollbild', accelerator: 'F11', click: () => this.act('fullscreen') },
      { type: 'separator' },
      { label: 'Auf Seite suchen', accelerator: 'Ctrl+F', click: () => this.act('find') },
      { label: 'Drucken …', accelerator: 'Ctrl+P', click: () => this.act('print') },
      { label: 'Als PDF speichern …', accelerator: 'Ctrl+Shift+P', click: () => this.act('save-pdf') },
      { label: 'Seite speichern …', accelerator: 'Ctrl+S', click: () => this.act('save-page') },
      { label: 'Entwicklerwerkzeuge', submenu: [
        { label: 'Untersuchen', accelerator: 'F12', click: () => this.act('devtools') },
        { label: 'Seitenquelltext', accelerator: 'Ctrl+U', click: () => this.act('view-source') },
      ] },
      { type: 'separator' },
      { label: 'Einstellungen', accelerator: 'Ctrl+,', click: () => this.act('settings') },
      { label: 'Nach Updates suchen', click: () => this.act('check-update') },
      { label: `Über ${APP_FULL}`, click: () => this.act('about') },
      { type: 'separator' },
      { label: 'Beenden', click: () => this.act('quit') },
    ];
    Menu.buildFromTemplate(tpl).popup({ window: this.win, x: Math.round(x), y: Math.round(y) });
  }

  showTabMenu(id, x, y) {
    const t = this.tab(id);
    if (!t) return;
    const wc = t.view ? t.view.webContents : null;
    Menu.buildFromTemplate([
      { label: 'Neuer Tab', click: () => this.act('new-tab') },
      { label: 'Neu laden', click: () => (wc ? wc.reload() : this.activate(id)) },
      { label: 'Duplizieren', click: () => this.act('duplicate', id) },
      { label: t.pinned ? 'Loslösen' : 'Anheften', click: () => this.act('pin', id) },
      { label: wc && wc.isAudioMuted() ? 'Ton einschalten' : 'Tab stummschalten', enabled: !!wc, click: () => this.act('mute', id) },
      { type: 'separator' },
      { label: 'Tab schließen', click: () => this.closeTab(id) },
      { label: 'Andere Tabs schließen', click: () => this.act('close-others', id) },
      { label: 'Tabs rechts schließen', click: () => this.act('close-right', id) },
      { label: 'Geschlossenen Tab wiederherstellen', click: () => this.act('reopen-tab') },
    ]).popup({ window: this.win, x: Math.round(x), y: Math.round(y) });
  }

  showSiteMenu(url, x, y) {
    Menu.buildFromTemplate([
      { label: 'In neuem Tab öffnen', click: () => this.newTab(url) },
      { label: 'Seitenfenster neu laden', enabled: this.panels.has(url), click: () => this.panels.get(url).webContents.reload() },
      { type: 'separator' },
      { label: 'Aus Seitenleiste entfernen', click: () => removeSidebarSite(url) },
    ]).popup({ window: this.win, x: Math.round(x), y: Math.round(y) });
  }

  showAccountMenu(x, y) {
    const acc = CFG.account;
    if (!acc) return this.openInternal('settings#konto');
    Menu.buildFromTemplate([
      { label: acc.name, enabled: false },
      { type: 'separator' },
      { label: 'Profil bearbeiten', click: () => this.openInternal('settings#konto') },
      acc.pw ? { label: 'Abmelden und sperren', click: () => lockAll() } : { label: 'Passwort festlegen …', click: () => this.openInternal('settings#konto') },
    ]).popup({ window: this.win, x: Math.round(x), y: Math.round(y) });
  }

  showBookmarkMenu(url, x, y) {
    Menu.buildFromTemplate([
      { label: 'In neuem Tab öffnen', click: () => this.newTab(url, { background: true }) },
      { label: 'In privatem Fenster öffnen', click: () => createWindow({ private: true, urls: [url] }) },
      { type: 'separator' },
      { label: 'Lesezeichen löschen', click: () => { CFG.bookmarks = CFG.bookmarks.filter((b) => b.url !== url); saveLater(); broadcastState(); } },
    ]).popup({ window: this.win, x: Math.round(x), y: Math.round(y) });
  }

  onClosed() {
    for (const t of this.tabs) this.destroyView(t);
    WINDOWS.delete(this);
    if (this.private) this.ses.clearStorageData().catch(() => {});
  }
}

function safeName(s) { return (s || 'seite').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80) || 'seite'; }

function publicConfig() {
  const { history, permissions, account, ...rest } = CFG;
  return { ...rest, account: account ? { name: account.name, color: account.color, hasPw: !!account.pw, avatar: !!account.avatar, created: account.created } : null, engines: Object.keys(SEARCH_ENGINES), accents: Object.keys(ACCENTS) };
}

function broadcastState() {
  for (const w of WINDOWS) {
    w.sendState();
    const t = theme();
    try { w.win.setTitleBarOverlay({ color: t.bg, symbolColor: t.text, height: 40 }); } catch (e) { /* egal */ }
    w.win.setBackgroundColor(t.bg);
  }
  nativeTheme.themeSource = CFG.dark_mode ? 'dark' : 'light';
  // interne Seiten (Startseite usw.) informieren
  for (const w of WINDOWS) for (const tab of w.tabs) {
    if (tab.view && !tab.view.webContents.isDestroyed() && isInternal(tab.view.webContents.getURL())) tab.view.webContents.send('page-state', pageState());
  }
}

function removeSidebarSite(url) {
  CFG.sidebar = CFG.sidebar.filter((s) => s.url !== url);
  saveLater();
  for (const w of WINDOWS) w.removePanel(url);
  broadcastState();
}

function createWindow(opts = {}) {
  const w = new NyroxWindow(opts);
  const urls = opts.urls && opts.urls.length ? opts.urls : [opts.private ? NEWTAB : homeUrl()];
  urls.forEach((u, i) => w.newTab(u, { background: i > 0, lazy: i > 0 }));
  if (urls.length > 1) w.activate(w.tabs[0].id);
  return w;
}

// ====================================================================== Sitzung
let sessionTimer = null;
function saveSession() {
  const urls = [];
  for (const w of WINDOWS) {
    if (w.private) continue;
    for (const t of w.tabs) {
      const u = t.view && !t.view.webContents.isDestroyed() ? t.view.webContents.getURL() || t.url : t.url;
      if (u && !isNewtab(u) && !u.startsWith('nyrox://error')) urls.push(u);
    }
  }
  CFG.session = urls;
  saveLater();
}
function saveSessionLater() { clearTimeout(sessionTimer); sessionTimer = setTimeout(saveSession, 2000); }

// ====================================================================== Konto & Sperre
function lockAll() {
  if (!CFG.account || !CFG.account.pw) return;
  for (const w of WINDOWS) w.setLocked(true);
}

// ====================================================================== Updater
let pendingUpdate = null;
async function fetchText(url) {
  const r = await fetch(url + (url.includes('?') ? '&' : '?') + 't=' + Date.now(), { cache: 'no-store' });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.text();
}
async function checkOnlineUpdate(manual) {
  try {
    if (manual) broadcastBanner('Suche nach Updates …');
    const info = JSON.parse(await fetchText(UPDATE_BASE + 'version.json'));
    if (!newer(info.version, VERSION) || (pendingUpdate && !newer(info.version, pendingUpdate))) {
      if (manual) broadcastBanner(pendingUpdate ? `Update ${pendingUpdate} ist bereit – bitte neu starten.` : `Du hast die neueste Version (${VERSION}).`, pendingUpdate ? 'Jetzt neu starten' : null, pendingUpdate ? 'restart' : null);
      return;
    }
    const staging = path.join(DATA, 'core-download');
    fs.rmSync(staging, { recursive: true, force: true });
    for (const f of ['version.json', ...info.files]) {
      const text = await fetchText(UPDATE_BASE + f);
      if (!text.length) throw new Error('Leere Datei: ' + f);
      if (f.endsWith('.js')) new vm.Script(text, { filename: f }); // Syntax prüfen – kaputte Updates nicht installieren
      const dest = path.join(staging, f);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.writeFileSync(dest, text);
    }
    const target = path.join(DATA, 'core');
    fs.rmSync(target, { recursive: true, force: true });
    fs.renameSync(staging, target);
    pendingUpdate = info.version;
    broadcastBanner(`Update auf Version ${info.version} ist bereit.`, 'Jetzt neu starten', 'restart');
  } catch (e) {
    if (manual) broadcastBanner('Update fehlgeschlagen: ' + e.message);
    log('Update: ' + e.message);
  }
}
function watchDevCore() {
  if (CORE_KIND !== 'dev') return;
  const vf = path.join(CORE_DIR, 'version.json');
  fs.watchFile(vf, { interval: 4000 }, () => {
    try {
      const v = JSON.parse(fs.readFileSync(vf, 'utf8')).version;
      if (newer(v, VERSION)) broadcastBanner(`Update auf Version ${v} ist bereit.`, 'Jetzt neu starten', 'restart');
    } catch (e) { /* Datei wird gerade geschrieben */ }
  });
}
function restartApp() {
  saveSession();
  saveConfig();
  CFG.running = false;
  saveConfig();
  app.relaunch();
  app.exit(0);
}

// ====================================================================== IPC: Oberfläche
function W(e) { return windowOfContents(e.sender); }
ipcMain.on('ui:act', (e, action, arg) => { const w = W(e); if (w) w.act(action, arg); });
ipcMain.on('ui:activate', (e, id) => { const w = W(e); if (w) w.activate(id); });
ipcMain.on('ui:close-tab', (e, id) => { const w = W(e); if (w) w.closeTab(id); });
ipcMain.on('ui:move-tab', (e, id, to) => { const w = W(e); if (w) w.moveTab(id, to); });
ipcMain.on('ui:layout', (e, rect, panelRect) => { const w = W(e); if (w) { w.contentRect = rect; w.panelRect = panelRect; w.layout(); } });
ipcMain.on('ui:open', (e, url, bg) => { const w = W(e); if (w) { if (bg) w.newTab(url, { background: true }); else w.act('navigate', url); } });
ipcMain.on('ui:panel', (e, url) => { const w = W(e); if (w) w.togglePanel(url); });
ipcMain.on('ui:panel-act', (e, a) => { const w = W(e); if (w) w.panelAction(a); });
ipcMain.on('ui:panel-width', (e, px) => { CFG.panel_width = Math.max(300, Math.min(900, px)); saveLater(); });
ipcMain.on('ui:menu', (e, kind, arg, x, y) => {
  const w = W(e);
  if (!w) return;
  if (kind === 'main') w.showMainMenu(x, y);
  if (kind === 'tab') w.showTabMenu(arg, x, y);
  if (kind === 'site') w.showSiteMenu(arg, x, y);
  if (kind === 'account') w.showAccountMenu(x, y);
  if (kind === 'bookmark') w.showBookmarkMenu(arg, x, y);
});
ipcMain.on('ui:window', (e, a) => {
  const w = W(e);
  if (!w) return;
  if (a === 'min') w.win.minimize();
  if (a === 'max') (w.win.isMaximized() ? w.win.unmaximize() : w.win.maximize());
  if (a === 'close') w.win.close();
});
ipcMain.handle('ui:suggest', (e, text) => {
  text = (text || '').toLowerCase();
  if (!text || text.length < 2) return '';
  const strip = (u) => u.replace(/^https?:\/\/(www\.)?/i, '');
  const pool = [...CFG.bookmarks.map((b) => b.url), ...CFG.history.slice().reverse().map((h) => h.url)];
  for (const u of pool) {
    const s = strip(u);
    if (s.toLowerCase().startsWith(text)) {
      const host = s.split('/')[0];
      return host.toLowerCase().startsWith(text) ? host : s;
    }
  }
  return '';
});
ipcMain.handle('ui:unlock', (e, pw) => {
  const acc = CFG.account;
  if (!acc || !acc.pw) return true;
  if (hashPw(pw || '', acc.salt) === acc.pw) { for (const w of WINDOWS) w.setLocked(false); return true; }
  return false;
});
ipcMain.on('ui:add-site', async (e) => {
  const w = W(e);
  if (!w) return;
  const t = w.activeTab();
  const u = t && t.view ? t.view.webContents.getURL() : '';
  if (!u || isInternal(u)) { w.banner('Öffne zuerst die Seite, die du hinzufügen möchtest, und klick dann auf +.'); return; }
  if (CFG.sidebar.some((s) => s.url === u)) return;
  CFG.sidebar.push({ title: t.title || hostOf(u), url: u });
  saveLater();
  broadcastState();
  w.banner(`${t.title || hostOf(u)} zur Seitenleiste hinzugefügt`);
});

// ====================================================================== IPC: interne Seiten (nyrox://)
function pageState() {
  return { version: VERSION, appName: APP_FULL, cfg: publicConfig(), theme: theme(), avatar: avatarDataUrl(), coreKind: CORE_KIND, chrome: CHROME_VERSION, electron: process.versions.electron, widevine: widevineStatus };
}
function fromInternal(e) {
  const u = e.senderFrame ? e.senderFrame.url : e.sender.getURL();
  return isInternal(u);
}
ipcMain.handle('page:state', (e) => (fromInternal(e) ? pageState() : null));
ipcMain.handle('page:history', (e, q) => {
  if (!fromInternal(e)) return [];
  q = (q || '').toLowerCase();
  const out = [];
  for (let i = CFG.history.length - 1; i >= 0 && out.length < 1000; i--) {
    const h = CFG.history[i];
    if (!q || (h.title || '').toLowerCase().includes(q) || h.url.toLowerCase().includes(q)) out.push({ ...h, index: i });
  }
  return out;
});
ipcMain.handle('page:history-delete', (e, idx) => { if (fromInternal(e)) { CFG.history.splice(idx, 1); saveLater(); } return true; });
ipcMain.handle('page:clear-data', async (e, what) => {
  if (!fromInternal(e)) return false;
  if (what.history) CFG.history = [];
  const storages = [];
  if (what.cookies) storages.push('cookies', 'localstorage', 'indexdb', 'serviceworkers', 'cachestorage');
  if (storages.length) await session.defaultSession.clearStorageData({ storages });
  if (what.cache) await session.defaultSession.clearCache();
  saveConfig();
  return true;
});
ipcMain.handle('page:downloads', (e) => (fromInternal(e) ? downloadsPublic() : []));
ipcMain.handle('page:download-act', (e, id, a) => {
  if (!fromInternal(e)) return false;
  const d = DOWNLOADS.find((x) => x.id === id);
  if (!d) return false;
  if (a === 'open') shell.openPath(d.path);
  if (a === 'folder') shell.showItemInFolder(d.path);
  if (a === 'cancel' && d.item) d.item.cancel();
  if (a === 'pause' && d.item) (d.item.isPaused() ? d.item.resume() : d.item.pause());
  if (a === 'remove') DOWNLOADS.splice(DOWNLOADS.indexOf(d), 1);
  broadcast('downloads', downloadsPublic());
  return true;
});
const ALLOWED_SETTINGS = ['homepage', 'search_engine', 'dark_mode', 'accent', 'adblock', 'block_popups', 'restore_session',
  'show_bookmarks', 'show_sidebar', 'hardware_accel', 'sleep_tabs', 'ask_download', 'download_dir', 'bookmarks', 'sidebar'];
ipcMain.handle('page:set', (e, key, value) => {
  if (!fromInternal(e) || !ALLOWED_SETTINGS.includes(key)) return false;
  const gpuChanged = key === 'hardware_accel' && !!value !== !!CFG.hardware_accel;
  CFG[key] = value;
  saveConfig();
  broadcastState();
  if (gpuChanged) broadcastBanner('Die Grafikeinstellung wird nach einem Neustart aktiv.', 'Jetzt neu starten', 'restart');
  return true;
});
ipcMain.handle('page:pick-folder', async (e) => {
  if (!fromInternal(e)) return null;
  const w = windowOfContents(e.sender);
  const r = await dialog.showOpenDialog(w ? w.win : undefined, { properties: ['openDirectory'], defaultPath: CFG.download_dir });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle('page:account-save', async (e, data) => {
  if (!fromInternal(e)) return { ok: false };
  const name = String(data.name || '').trim().slice(0, 40);
  if (!name) return { ok: false, error: 'Bitte gib einen Namen ein.' };
  const acc = CFG.account || { created: new Date().toLocaleDateString('de-DE') };
  acc.name = name;
  if (!acc.color) acc.color = ['#25d366', '#5865f2', '#e1306c', '#1db954', '#9146ff', '#0ea5e9', '#f59e0b', '#fa1e4e'][name.length % 8];
  if (data.password) {
    if (String(data.password).length < 4) return { ok: false, error: 'Das Passwort muss mindestens 4 Zeichen haben.' };
    acc.salt = crypto.randomBytes(16).toString('hex');
    acc.pw = hashPw(String(data.password), acc.salt);
  } else if (data.removePassword) {
    acc.pw = '';
  }
  if (!acc.pw) acc.pw = '';
  CFG.account = acc;
  saveConfig();
  broadcastState();
  return { ok: true };
});
ipcMain.handle('page:account-avatar', async (e) => {
  if (!fromInternal(e)) return false;
  const w = windowOfContents(e.sender);
  const r = await dialog.showOpenDialog(w ? w.win : undefined, { properties: ['openFile'], filters: [{ name: 'Bilder', extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'] }] });
  if (r.canceled || !r.filePaths[0]) return false;
  const img = nativeImage.createFromPath(r.filePaths[0]);
  if (img.isEmpty()) return false;
  const size = img.getSize(); const side = Math.min(size.width, size.height);
  const square = img.crop({ x: Math.floor((size.width - side) / 2), y: Math.floor((size.height - side) / 2), width: side, height: side }).resize({ width: 256, height: 256, quality: 'best' });
  fs.writeFileSync(AVATAR_FILE, square.toPNG());
  if (!CFG.account) CFG.account = { name: 'Ich', pw: '', created: new Date().toLocaleDateString('de-DE') };
  CFG.account.avatar = 'avatar.png';
  saveConfig();
  broadcastState();
  return true;
});
ipcMain.handle('page:account-delete', (e) => {
  if (!fromInternal(e)) return false;
  CFG.account = null;
  try { fs.unlinkSync(AVATAR_FILE); } catch (err) { /* egal */ }
  saveConfig();
  broadcastState();
  return true;
});
ipcMain.on('page:open', (e, url, newTab) => {
  if (!fromInternal(e)) return;
  const w = windowOfContents(e.sender);
  if (!w) return;
  if (newTab) w.newTab(url, { background: true }); else w.act('navigate', url);
});
ipcMain.on('page:act', (e, action) => {
  if (!fromInternal(e)) return;
  const w = windowOfContents(e.sender);
  if (w && ['check-update', 'restart', 'focus-url'].includes(action)) w.act(action);
});

// ====================================================================== Start
let widevineStatus = 'unbekannt';
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', (e, argv) => {
    const urls = argv.slice(1).filter((a) => /^(https?|file):/i.test(a));
    const w = [...WINDOWS].find((x) => !x.private);
    if (w) {
      if (w.win.isMinimized()) w.win.restore();
      w.win.focus();
      urls.forEach((u) => w.newTab(u));
    } else createWindow({ urls });
  });

  app.whenReady().then(async () => {
    // Widevine (für Netflix, Spotify, Disney+ usw.) – nur in der castLabs-Version vorhanden
    if (electron.components && electron.components.whenReady) {
      try {
        await electron.components.whenReady();
        widevineStatus = 'aktiv';
      } catch (e) {
        widevineStatus = 'Fehler: ' + e.message;
        log('Widevine: ' + e.message);
      }
    } else {
      widevineStatus = 'nicht verfügbar';
    }
    nativeTheme.themeSource = CFG.dark_mode ? 'dark' : 'light';
    prepareSession(session.defaultSession);

    const crashed = !!CFG.running;
    CFG.running = true;
    saveConfig();

    const argUrls = process.argv.slice(1).filter((a) => /^(https?|file):/i.test(a));
    let urls = argUrls;
    if (!urls.length && (CFG.restore_session || crashed) && CFG.session && CFG.session.length) urls = CFG.session;
    const w = createWindow({ urls });

    const last = CFG.last_version;
    CFG.last_version = VERSION;
    saveLater();
    setTimeout(() => {
      if (crashed) w.banner('NyroxNite wurde unerwartet beendet. Deine Tabs wurden wiederhergestellt.');
      else if (last && last !== VERSION) w.banner(`${APP_FULL} wurde auf Version ${VERSION} aktualisiert.`, 'Neuigkeiten', 'about');
      else if (!last) w.banner(`Willkommen bei ${APP_FULL}! Twitch, Netflix & Co. funktionieren jetzt.`);
    }, 1500);

    watchDevCore();
    setTimeout(() => checkOnlineUpdate(false), 10000);
    setInterval(() => checkOnlineUpdate(false), UPDATE_INTERVAL);
    setInterval(() => { for (const x of WINDOWS) x.sleepTabs(); }, 60000);
  });

  app.on('window-all-closed', () => {
    saveConfig();
    app.quit();
  });
  app.on('before-quit', () => {
    if (WINDOWS.size) saveSession();
    CFG.running = false;
    saveConfig();
  });
}
