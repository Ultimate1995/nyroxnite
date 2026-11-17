// Gemeinsame Hilfen für interne Seiten (nyrox://)
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hostOf = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return u; } };
const COLORS = ['#25d366', '#5865f2', '#e1306c', '#1db954', '#ff0000', '#9146ff', '#0ea5e9', '#f59e0b'];
const colorFor = (s) => COLORS[[...String(s)].reduce((a, c) => a + c.charCodeAt(0), 0) % COLORS.length];
function favImg(url) {
  const img = document.createElement('img');
  img.src = 'https://www.google.com/s2/favicons?sz=64&domain_url=' + encodeURIComponent(url);
  img.onerror = () => {
    const s = document.createElement('span');
    s.className = 'letter';
    s.style.background = colorFor(hostOf(url));
    s.textContent = hostOf(url).charAt(0).toUpperCase();
    img.replaceWith(s);
  };
  return img;
}
function applyTheme(t) {
  const r = document.documentElement.style;
  for (const k of ['bg', 'surface', 'field', 'hover', 'border', 'text', 'muted', 'accent', 'accent2']) r.setProperty('--' + k, t[k]);
}
async function boot(render) {
  const s = await window.nyrox.state();
  applyTheme(s.theme);
  render(s);
  window.nyrox.onState((n) => { applyTheme(n.theme); render(n); });
}
function fmtBytes(b) {
  if (!b) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB']; let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return b.toFixed(i ? 1 : 0) + ' ' + u[i];
}
