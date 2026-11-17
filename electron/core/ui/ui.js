// NyroxNite Browser – Logik der Oberfläche
'use strict';
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const api = window.nyrox;

let STATE = { cfg: {}, theme: {} };
let TABS = { tabs: [], active: null };
let lastUrlTyped = '';

// ---------- Hilfen
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
const COLORS = ['#25d366', '#5865f2', '#e1306c', '#1db954', '#ff0000', '#9146ff', '#0ea5e9', '#f59e0b'];
const colorFor = (s) => COLORS[[...String(s)].reduce((a, c) => a + c.charCodeAt(0), 0) % COLORS.length];
const favUrl = (u) => 'https://www.google.com/s2/favicons?sz=64&domain_url=' + encodeURIComponent(u);
function letter(text, color) {
  return `<span class="letter" style="background:${color || colorFor(text)}">${esc((text || '?').trim().charAt(0).toUpperCase())}</span>`;
}
function siteIcon(url, title) {
  // echtes Seiten-Symbol, bei Fehler ein farbiger Buchstabe
  const img = document.createElement('img');
  img.src = favUrl(url);
  img.alt = '';
  img.onerror = () => { img.outerHTML = letter(title || host(url), colorFor(host(url))); };
  return img;
}
function mix(hex, other, f) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const a = p(hex); const b = p(other);
  return '#' + a.map((v, i) => Math.round(v * f + b[i] * (1 - f)).toString(16).padStart(2, '0')).join('');
}

// ---------- Symbole einsetzen
function initIcons() {
  $$('[data-icon]').forEach((b) => { b.innerHTML = ICON(b.dataset.icon); });
  $('#logo').innerHTML = LOGO(26);
  $('#add-site').innerHTML = ICON('plus');
  $('#newtab').innerHTML = ICON('plus');
  $('#banner .bicon').innerHTML = ICON('sparkle');
}

// ---------- Zustand vom Hauptprozess
api.on('state', (s) => {
  STATE = s;
  applyTheme(s.theme);
  $('#privbadge').hidden = !s.private;
  renderSidebar();
  renderBookmarks();
  renderAccount();
  $('#btn-shield').innerHTML = ICON(s.cfg.adblock ? 'shield' : 'shieldOff');
  $('#btn-shield').classList.toggle('on', !!s.cfg.adblock);
  $('#btn-shield').title = s.cfg.adblock ? 'Werbeblocker: an' : 'Werbeblocker: aus';
  $('#btn-theme').innerHTML = ICON(s.theme.dark ? 'sun' : 'moon');
  $('#sidebar').hidden = !s.cfg.show_sidebar;
  if (!s.cfg.show_sidebar) $('#panel').hidden = true;
  $('#bookmarks').classList.toggle('hidden', !s.cfg.show_bookmarks);
  $('#panel').style.width = (s.cfg.panel_width || 420) + 'px';
  renderDownloads(s.downloads || []);
  setLocked(s.locked);
  renderTabs();
  sendLayout();
});

function applyTheme(t) {
  const r = document.documentElement.style;
  for (const k of ['bg', 'surface', 'field', 'hover', 'border', 'text', 'muted', 'accent', 'accent2']) r.setProperty('--' + k, t[k]);
  r.setProperty('--soft', mix(t.accent, t.surface, t.dark ? 0.22 : 0.12));
  document.body.classList.toggle('light', !t.dark);
}

// ---------- Tabs
api.on('tabs', (data) => {
  TABS = data;
  renderTabs();
  renderToolbar();
  $$('#sites .side').forEach((b) => b.classList.toggle('active', b.dataset.url === data.panel));
});

let dragId = null;
function renderTabs() {
  const box = $('#tabs');
  const frag = document.createDocumentFragment();
  for (const t of TABS.tabs) {
    const el = document.createElement('div');
    el.className = 'tab' + (t.id === TABS.active ? ' active' : '') + (t.pinned ? ' pinned' : '') + (t.discarded ? ' discarded' : '');
    el.draggable = true;
    el.dataset.id = t.id;
    el.title = t.title;
    const fav = document.createElement('span');
    fav.className = 'fav';
    if (t.loading) fav.innerHTML = '<span class="spinner"></span>';
    else if (t.crashed) fav.innerHTML = ICON('alert', { size: 15 });
    else if (!t.url) fav.innerHTML = LOGO(15);
    else if (t.favicon) { const i = document.createElement('img'); i.src = t.favicon; i.onerror = () => { fav.innerHTML = letter(host(t.url), colorFor(host(t.url))); fav.firstChild.style.cssText = 'width:16px;height:16px;font-size:10px'; }; fav.appendChild(i); }
    else fav.innerHTML = ICON('search', { size: 14 });
    el.appendChild(fav);
    el.insertAdjacentHTML('beforeend', `<span class="title">${esc(t.title)}</span>`);
    if (t.audible || t.muted) {
      const a = document.createElement('button');
      a.className = 'audio';
      a.title = t.muted ? 'Ton einschalten' : 'Stummschalten';
      a.innerHTML = ICON(t.muted ? 'mute' : 'volume', { size: 14 });
      a.onclick = (e) => { e.stopPropagation(); api.act('mute', t.id); };
      el.appendChild(a);
    }
    const c = document.createElement('button');
    c.className = 'close';
    c.title = 'Tab schließen';
    c.innerHTML = ICON('x', { size: 14 });
    c.onclick = (e) => { e.stopPropagation(); api.closeTab(t.id); };
    el.appendChild(c);
    el.onmousedown = (e) => { if (e.button === 0) api.activate(t.id); };
    el.onauxclick = (e) => { if (e.button === 1) { e.preventDefault(); api.closeTab(t.id); } };
    el.oncontextmenu = (e) => { e.preventDefault(); api.menu('tab', t.id, e.clientX, e.clientY); };
    el.ondragstart = (e) => { dragId = t.id; el.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; };
    el.ondragend = () => { dragId = null; $$('.tab').forEach((x) => x.classList.remove('dragging', 'drop-before')); };
    el.ondragover = (e) => { if (dragId) { e.preventDefault(); $$('.tab').forEach((x) => x.classList.remove('drop-before')); el.classList.add('drop-before'); } };
    el.ondrop = (e) => {
      e.preventDefault();
      if (!dragId || dragId === t.id) return;
      const ids = TABS.tabs.map((x) => x.id);
      let to = ids.indexOf(t.id);
      if (ids.indexOf(dragId) < to) to -= 1;
      api.moveTab(dragId, to);
    };
    frag.appendChild(el);
  }
  box.replaceChildren(frag);
}
$('#tabs').addEventListener('dragover', (e) => { if (dragId) e.preventDefault(); });
$('#newtab').onclick = () => api.act('new-tab');

// ---------- Werkzeugleiste
function activeTab() { return TABS.tabs.find((t) => t.id === TABS.active); }
function renderToolbar() {
  const t = activeTab();
  if (!t) return;
  $('#btn-back').disabled = !t.canBack;
  $('#btn-forward').disabled = !t.canForward;
  const rb = $('#btn-reload');
  rb.innerHTML = ICON(t.loading ? 'stop' : 'reload');
  rb.title = t.loading ? 'Laden stoppen' : 'Neu laden (F5)';
  rb.dataset.loading = t.loading ? '1' : '';
  const url = $('#url');
  if (document.activeElement !== url) url.value = t.url;
  const icon = $('#urlicon');
  icon.classList.remove('warn');
  if (!t.url) icon.innerHTML = ICON('search', { size: 16 });
  else if (t.url.startsWith('https:') || t.url.startsWith('nyrox:')) icon.innerHTML = ICON('lock', { size: 15 });
  else if (t.url.startsWith('http:')) { icon.innerHTML = ICON('alert', { size: 16 }); icon.classList.add('warn'); }
  else icon.innerHTML = ICON('search', { size: 16 });
  icon.title = t.url.startsWith('https:') ? 'Verbindung ist sicher' : t.url.startsWith('http:') ? 'Verbindung ist nicht sicher' : '';
  const star = $('#star');
  star.hidden = !t.url || t.url.startsWith('nyrox:');
  star.innerHTML = ICON('star', { size: 16, fill: t.bookmarked ? 'currentColor' : 'none' });
  star.classList.toggle('on', !!t.bookmarked);
  const z = $('#zoom');
  z.hidden = t.zoom === 100;
  z.textContent = t.zoom + ' %';
  const lb = $('#loadbar');
  if (t.loading) { lb.className = ''; void lb.offsetWidth; lb.className = 'loading'; }
  else if (lb.classList.contains('loading')) { lb.className = 'done'; }
}
$('#btn-reload').onclick = () => api.act($('#btn-reload').dataset.loading ? 'stop' : 'reload');
$('#zoom').onclick = () => api.act('zoom-reset');
$('#star').onclick = () => api.act('bookmark');
$('#btn-shield').onclick = () => api.act('adblock');
$('#btn-theme').onclick = () => api.act('theme');
$('#btn-menu').onclick = (e) => { const r = e.currentTarget.getBoundingClientRect(); api.menu('main', null, r.right - 260, r.bottom + 4); };
$('#account').onclick = (e) => { const r = e.currentTarget.getBoundingClientRect(); api.menu('account', null, r.left, r.bottom + 4); };
$('#logo').onclick = (e) => { const r = e.currentTarget.getBoundingClientRect(); api.menu('main', null, r.right + 4, r.top); };
$$('[data-act]').forEach((b) => { b.addEventListener('click', () => api.act(b.dataset.act)); });

// ---------- Adressleiste mit Autovervollständigung
const url = $('#url');
url.addEventListener('focus', () => { $('#urlwrap').classList.add('focus'); setTimeout(() => url.select(), 0); });
url.addEventListener('blur', () => { $('#urlwrap').classList.remove('focus'); const t = activeTab(); if (t) url.value = t.url; });
url.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const v = url.value.trim();
    if (!v) return;
    if (e.altKey) api.open(v, true); else api.act('navigate', v);
    url.blur();
  } else if (e.key === 'Escape') {
    const t = activeTab();
    url.value = t ? t.url : '';
    url.select();
  }
});
url.addEventListener('input', async (e) => {
  const typed = url.value;
  const deleting = e.inputType && e.inputType.startsWith('delete');
  lastUrlTyped = typed;
  if (deleting || !typed || url.selectionStart !== typed.length) return;
  const s = await api.suggest(typed);
  if (s && lastUrlTyped === typed && url.value === typed && s.toLowerCase().startsWith(typed.toLowerCase()) && s.length > typed.length) {
    url.value = typed + s.slice(typed.length);
    url.setSelectionRange(typed.length, url.value.length);
  }
});
api.on('focus-url', () => { url.focus(); url.select(); });

// ---------- Lesezeichenleiste
function renderBookmarks() {
  const box = $('#bookmarks');
  box.replaceChildren();
  const list = STATE.cfg.bookmarks || [];
  if (!list.length) {
    box.innerHTML = '<span class="bm empty">Lesezeichen mit Strg+D hinzufügen</span>';
    return;
  }
  for (const b of list) {
    const el = document.createElement('button');
    el.className = 'bm';
    el.title = b.url;
    el.appendChild(siteIcon(b.url, b.title));
    el.insertAdjacentHTML('beforeend', `<span>${esc(b.title)}</span>`);
    el.onclick = (e) => { if (e.ctrlKey) api.open(b.url, true); else api.act('navigate', b.url); };
    el.onauxclick = (e) => { if (e.button === 1) api.open(b.url, true); };
    el.oncontextmenu = (e) => { e.preventDefault(); api.menu('bookmark', b.url, e.clientX, e.clientY); };
    box.appendChild(el);
  }
}

// ---------- Seitenleiste & Seitenfenster
function renderSidebar() {
  const box = $('#sites');
  box.replaceChildren();
  for (const s of STATE.cfg.sidebar || []) {
    const b = document.createElement('button');
    b.className = 'side' + (TABS.panel === s.url ? ' active' : '');
    b.title = s.title;
    b.dataset.url = s.url;
    b.appendChild(siteIcon(s.url, s.title));
    b.onclick = () => api.panel(s.url);
    b.oncontextmenu = (e) => { e.preventDefault(); api.menu('site', s.url, e.clientX, e.clientY); };
    box.appendChild(b);
  }
}
$('#add-site').onclick = () => api.addSite();
api.on('panel', (p) => {
  $('#panel').hidden = !p;
  if (p) $('#panel-title').textContent = p.title;
  requestAnimationFrame(sendLayout);
});
$$('[data-panel]').forEach((b) => {
  b.onclick = () => {
    if (b.dataset.panel === 'close') api.panel(TABS.panel);
    else api.panelAct(b.dataset.panel);
  };
});
(() => {
  const rz = $('#panel-resizer');
  let startX = 0; let startW = 0;
  const move = (e) => {
    const w = Math.max(300, Math.min(900, startW + e.clientX - startX));
    $('#panel').style.width = w + 'px';
    sendLayout();
  };
  const up = () => {
    window.removeEventListener('mousemove', move);
    window.removeEventListener('mouseup', up);
    api.panelWidth(parseInt($('#panel').style.width, 10));
  };
  rz.addEventListener('mousedown', (e) => {
    startX = e.clientX; startW = $('#panel').getBoundingClientRect().width;
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  });
})();

// ---------- Konto
function renderAccount() {
  const b = $('#account');
  const acc = STATE.cfg.account;
  if (!acc) {
    b.className = '';
    b.innerHTML = `<span class="uicon">${ICON('user', { size: 17 })}</span>Konto erstellen`;
    b.title = 'Lokales Konto erstellen';
  } else {
    b.className = 'has';
    b.innerHTML = STATE.avatar ? `<img src="${STATE.avatar}" alt="">` : letter(acc.name, acc.color);
    b.title = 'Angemeldet als ' + acc.name;
  }
}

// ---------- Sperrbildschirm
function setLocked(locked) {
  $('#lock').hidden = !locked;
  if (!locked) return;
  const acc = STATE.cfg.account || {};
  $('#lock-avatar').innerHTML = STATE.avatar ? `<img src="${STATE.avatar}" alt="">` : esc((acc.name || '?').charAt(0).toUpperCase());
  $('#lock-avatar').style.background = STATE.avatar ? 'none' : (acc.color || 'var(--accent)');
  $('#lock-title').textContent = 'Willkommen zurück, ' + (acc.name || '');
  $('#lock-error').textContent = '';
  setTimeout(() => $('#lock-pw').focus(), 50);
}
api.on('locked', setLocked);
let tries = 0;
async function tryUnlock() {
  const pw = $('#lock-pw').value;
  const ok = await api.unlock(pw);
  $('#lock-pw').value = '';
  if (ok) { tries = 0; return; }
  tries += 1;
  $('#lock-error').textContent = 'Falsches Passwort.' + (tries >= 3 ? ' Bitte warte kurz …' : '');
  if (tries >= 3) {
    $('#lock-pw').disabled = true;
    setTimeout(() => { $('#lock-pw').disabled = false; $('#lock-pw').focus(); }, 3000 * (tries - 2));
  }
}
$('#lock-btn').onclick = tryUnlock;
$('#lock-pw').addEventListener('keydown', (e) => { if (e.key === 'Enter') tryUnlock(); });

// ---------- Hinweise (Banner)
let bannerTimer = null;
api.on('banner', ({ text, button, action }) => {
  $('#banner-text').textContent = text;
  const btn = $('#banner-btn');
  btn.hidden = !button;
  btn.textContent = button || '';
  btn.onclick = () => { $('#banner').hidden = true; sendLayout(); if (action) api.act(action); };
  $('#banner').hidden = false;
  sendLayout();
  clearTimeout(bannerTimer);
  if (!button || /^Download fertig/.test(text)) bannerTimer = setTimeout(() => { $('#banner').hidden = true; sendLayout(); }, button ? 8000 : 4000);
});
$('#banner-close').onclick = () => { $('#banner').hidden = true; sendLayout(); };

// ---------- Auf Seite suchen
const find = $('#find');
api.on('find-open', () => { $('#findbar').hidden = false; sendLayout(); find.focus(); find.select(); if (find.value) doFind(false, false); });
function doFind(next, back) { api.act('find-text', { text: find.value, next, back, matchCase: $('#find-case').checked }); }
function closeFind() { $('#findbar').hidden = true; $('#find-count').textContent = ''; api.act('find-close'); sendLayout(); }
find.addEventListener('input', () => { if (!find.value) $('#find-count').textContent = ''; doFind(false, false); });
find.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doFind(true, e.shiftKey);
  if (e.key === 'Escape') closeFind();
});
$('#find-next').onclick = () => doFind(true, false);
$('#find-prev').onclick = () => doFind(true, true);
$('#find-close').onclick = closeFind;
$('#find-case').onchange = () => doFind(false, false);
api.on('find-result', (r) => { $('#find-count').textContent = r.matches ? `${r.active} von ${r.matches}` : 'Keine Treffer'; });

// ---------- Downloads (Fortschrittsring am Symbol)
function renderDownloads(list) {
  const active = list.filter((d) => d.state === 'progressing');
  const ring = $('#dl-ring');
  $('#btn-dl').innerHTML = ICON('download');
  $('#btn-dl').appendChild(ring);
  if (!active.length) { ring.style.background = 'none'; return; }
  const total = active.reduce((a, d) => a + (d.total || 0), 0);
  const rec = active.reduce((a, d) => a + (d.received || 0), 0);
  const p = total ? Math.round((rec / total) * 100) : 30;
  ring.style.background = `conic-gradient(var(--accent) ${p}%, transparent 0)`;
  ring.style.webkitMask = 'radial-gradient(farthest-side, transparent calc(100% - 2.5px), #000 calc(100% - 2px))';
}
api.on('downloads', renderDownloads);

// ---------- Link-Vorschau unten links
// (Link-Vorschau wird in der Adressleiste als Tooltip gezeigt – über der Webseite kann nichts liegen)
api.on('hover-link', (u) => { $('#urlwrap').title = u || ''; });

// ---------- Vollbild & Fenster
api.on('fullscreen', (on) => { document.body.classList.toggle('fullscreen', !!on); requestAnimationFrame(sendLayout); });

// ---------- Layout an den Hauptprozess melden (dort liegt die echte Webseite)
let layoutQueued = false;
function sendLayout() {
  if (layoutQueued) return;
  layoutQueued = true;
  requestAnimationFrame(() => {
    layoutQueued = false;
    const r = $('#content').getBoundingClientRect();
    const panelOpen = !$('#panel').hidden && !$('#sidebar').hidden;
    const p = panelOpen ? $('#panel-content').getBoundingClientRect() : null;
    api.layout({ x: r.left, y: r.top, width: r.width, height: r.height },
      p ? { x: p.left, y: p.top, width: Math.max(0, p.width - 5), height: p.height } : null); // 5 px frei für den Ziehgriff
  });
}
new ResizeObserver(sendLayout).observe($('#content'));
new ResizeObserver(sendLayout).observe($('#panel-content'));
window.addEventListener('resize', sendLayout);

initIcons();
sendLayout();
