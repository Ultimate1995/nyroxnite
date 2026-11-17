// NyroxNite Browser – Starter.
// Lädt immer die neueste verfügbare Version des Browsers ("core"):
//   1. Entwickler-Ordner (z. B. D:\NovaBrowser\electron\core) – für lokale Updates
//   2. Online heruntergeladenes Update (%APPDATA%\NyroxNite Browser\core)
//   3. Die mitgelieferte Version in der EXE
const path = require('path');
const fs = require('fs');
const { app, dialog } = require('electron');

app.setName('NyroxNite Browser');
app.setPath('userData', path.join(app.getPath('appData'), 'NyroxNite Browser'));

function readVersion(dir) {
  try {
    const v = JSON.parse(fs.readFileSync(path.join(dir, 'version.json'), 'utf8')).version;
    return String(v).split('.').map((n) => parseInt(n, 10) || 0);
  } catch (e) {
    return null;
  }
}

function cmp(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] || 0) - (b[i] || 0);
    if (d) return d;
  }
  return 0;
}

function candidates() {
  const list = [];
  // Entwickler-Ordner: neben der EXE bzw. bis zu 4 Ordner darüber
  let dir = path.dirname(process.execPath);
  for (let i = 0; i < 5; i++) {
    const c = path.join(dir, 'core');
    if (fs.existsSync(path.join(c, 'version.json')) && fs.existsSync(path.join(c, 'main.js'))) {
      list.push({ dir: c, kind: 'dev' });
      break;
    }
    dir = path.dirname(dir);
  }
  list.push({ dir: path.join(app.getPath('userData'), 'core'), kind: 'online' });
  list.push({ dir: path.join(__dirname, 'core'), kind: 'bundled' });
  const seen = new Set();
  return list
    .filter((c) => {
      const key = path.resolve(c.dir).toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((c) => ({ ...c, version: readVersion(c.dir) }))
    .filter((c) => c.version)
    .sort((a, b) => cmp(b.version, a.version)); // stabil: bei Gleichstand Reihenfolge oben
}

const errors = [];
let started = false;
for (const c of candidates()) {
  try {
    process.env.NYROX_CORE_DIR = c.dir;
    process.env.NYROX_CORE_KIND = c.kind;
    process.env.NYROX_BUNDLED_CORE = path.join(__dirname, 'core');
    require(path.join(c.dir, 'main.js'));
    started = true;
    break;
  } catch (e) {
    errors.push(`${c.dir}:\n${e && e.stack ? e.stack : e}`);
  }
}

if (!started) {
  app.whenReady().then(() => {
    dialog.showErrorBox('NyroxNite Browser – Fehler',
      'Der Browser konnte nicht gestartet werden.\n\n' + (errors.join('\n\n') || 'Keine Programmdateien gefunden.'));
    app.quit();
  });
}
