#!/usr/bin/env python3
"""
NyroxNite by Tobias – moderner Desktop-Browser auf Basis von Chromium (QtWebEngine).

Start:   python browser.py      (oder NyroxNite.exe nach dem Bauen)
Pakete:  pip install PyQt6 PyQt6-WebEngine

Updater: Die EXE lädt diese Datei bei jedem Start neu. Wird browser.py verändert,
         merkt der laufende Browser das sofort und bietet einen Neustart an –
         offene Tabs bleiben dabei erhalten.
"""

VERSION = "2.4.0"
CHANGELOG = {
    "2.4.0": [
        "Online-Updates sind eingeschaltet: Updates kommen jetzt auf jeden PC",
    ],
    "2.3.0": [
        "Absturzschutz: Nach einem Absturz startet NyroxNite im abgesicherten Grafikmodus",
        "Tabs werden laufend gesichert und nach einem Absturz wiederhergestellt",
        "Abgestürzte Seiten können mit einem Klick neu geladen werden",
        "Neue Einstellung: Hardwarebeschleunigung an/aus",
    ],
    "2.2.0": [
        "Online-Updates: NyroxNite aktualisiert sich auf jedem PC automatisch",
    ],
    "2.1.0": [
        "Neuer Name: NyroxNite by Tobias",
    ],
    "2.0.0": [
        "Komplett neues Design mit hellem und dunklem Thema",
        "Tabs oben wie bei modernen Browsern, eigene Symbole",
        "Neue Startseite mit Uhr, Suche und Schnellzugriff",
        "Akzentfarbe wählbar (Indigo, Blau, Grün, Rosa, Orange)",
        "Automatischer Updater mit Neustart-Hinweis",
        "Fehler werden protokolliert statt den Browser zu beenden",
    ],
}

import hashlib
import html
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from PyQt6.QtCore import (Qt, QUrl, QSize, QTimer, QObject, pyqtSignal, QByteArray, QStringListModel,
                          QFileSystemWatcher, QProcess, QEvent)
from PyQt6.QtGui import (QAction, QIcon, QKeySequence, QPalette, QColor, QDesktopServices, QShortcut,
                         QPixmap, QPainter)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QStackedWidget, QToolButton,
    QToolBar, QLineEdit, QProgressBar, QLabel, QFrame, QDialog, QListWidget, QListWidgetItem, QPushButton,
    QFileDialog, QMessageBox, QComboBox, QCheckBox, QCompleter, QMenu, QInputDialog, QFormLayout,
    QDialogButtonBox,
)
from PyQt6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
                                   QWebEngineDownloadRequest, QWebEngineUrlRequestInterceptor)
from PyQt6.QtWebEngineWidgets import QWebEngineView

# ====================================================================== Online-Updates
# Adresse, unter der die neueste browser.py liegt (z. B. GitHub "raw"-Link).
# Leer = nur lokale Updates auf dem Entwickler-PC.
UPDATE_URL = "https://raw.githubusercontent.com/Ultimate1995/nyroxnite/main/browser.py"
UPDATE_INTERVAL_MIN = 30

# ====================================================================== Pfade
APP_NAME = "NyroxNite"
APP_FULL = "NyroxNite by Tobias"
APP_FILE = Path(__file__).resolve()
try:
    START_HASH = hashlib.sha1(APP_FILE.read_bytes()).hexdigest()
except Exception:
    START_HASH = ""

_APPDATA = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
DATA_DIR = _APPDATA / APP_NAME
if not DATA_DIR.exists() and (_APPDATA / "NovaBrowser").exists():
    try:  # Daten (Lesezeichen, Verlauf, Logins) vom alten Namen übernehmen
        (_APPDATA / "NovaBrowser").rename(DATA_DIR)
    except Exception:
        DATA_DIR = _APPDATA / "NovaBrowser"  # Ordner gerade in Benutzung -> beim nächsten Start
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPDATE_DIR = DATA_DIR / "app"          # hier landen heruntergeladene Updates
UPDATE_DIR.mkdir(exist_ok=True)
ICON_DIR = DATA_DIR / "icons"
ICON_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
NEWTAB_FILE = DATA_DIR / "newtab.html"
LOG_FILE = DATA_DIR / "fehler.log"
CRASH_FILE = DATA_DIR / "absturz.log"

SEARCH_ENGINES = {
    "Google": "https://www.google.com/search?q={}",
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Bing": "https://www.bing.com/search?q={}",
    "Ecosia": "https://www.ecosia.org/search?q={}",
    "Startpage": "https://www.startpage.com/do/search?q={}",
}

AD_HOSTS = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adservice.google.com",
    "ads.yahoo.com", "adnxs.com", "taboola.com", "outbrain.com", "criteo.com", "scorecardresearch.com",
    "zedo.com", "pubmatic.com", "rubiconproject.com", "openx.net", "moatads.com", "amazon-adsystem.com",
    "advertising.com", "adform.net", "smartadserver.com", "casalemedia.com", "media.net",
}

ACCENTS = {
    "Indigo": ("#6366f1", "#8b5cf6"),
    "Blau": ("#2563eb", "#0ea5e9"),
    "Grün": ("#059669", "#14b8a6"),
    "Rosa": ("#db2777", "#f472b6"),
    "Orange": ("#ea580c", "#f59e0b"),
}

LIGHT = dict(bg="#eceef3", surface="#ffffff", field="#f1f3f6", hover="#e5e7ed", pressed="#d9dce4",
             border="#e1e4ea", border2="#c7ccd6", text="#1d2129", muted="#6b7280", warn="#e11d48")
DARK = dict(bg="#121317", surface="#1e1f24", field="#2a2b31", hover="#303139", pressed="#3a3c45",
            border="#2c2e35", border2="#4a4d58", text="#e8e9ee", muted="#9ca3af", warn="#fb7185")

DEFAULT_CONFIG = {
    "homepage": "",            # leer = NyroxNite-Startseite
    "search_engine": "DuckDuckGo",
    "dark_mode": False,
    "accent": "Indigo",
    "force_dark_web": False,
    "adblock": True,
    "block_popups": False,
    "javascript": True,
    "restore_session": True,
    "show_bookmarks": True,
    "download_dir": str(Path.home() / "Downloads"),
    "bookmarks": [
        {"title": "Wikipedia", "url": "https://de.wikipedia.org"},
        {"title": "YouTube", "url": "https://www.youtube.com"},
        {"title": "GitHub", "url": "https://github.com"},
    ],
    "history": [],
    "session": [],
    "zoom": {},
    "last_version": "",
    "restore_once": False,
    "hardware_accel": True,
    "running": False,
    "crash_count": 0,
}


# ====================================================================== Konfiguration
class Config:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))
        if CONFIG_FILE.exists():
            try:
                self.data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass
        if self.data.get("homepage") == "https://duckduckgo.com" and not self.data.get("last_version"):
            self.data["homepage"] = ""  # alte Standard-Startseite -> neue Startseite

    def __getitem__(self, k):
        return self.data.get(k, DEFAULT_CONFIG.get(k))

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        self.data["history"] = self.data.get("history", [])[-5000:]
        try:
            CONFIG_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass


CFG = Config()
WINDOWS = []
DOWNLOADS = None
UPDATER = None
_profiles = {}
NEWTAB_URL = QUrl.fromLocalFile(str(NEWTAB_FILE))


def is_newtab(url):
    url = url if isinstance(url, QUrl) else QUrl(str(url))
    return url.isLocalFile() and Path(url.toLocalFile()).name == NEWTAB_FILE.name


def home_url():
    return QUrl(CFG["homepage"]) if CFG["homepage"].strip() else NEWTAB_URL


# ====================================================================== Thema & Symbole
def mix(c1, c2, f):
    a, b = QColor(c1), QColor(c2)
    return QColor(int(a.red() * f + b.red() * (1 - f)),
                  int(a.green() * f + b.green() * (1 - f)),
                  int(a.blue() * f + b.blue() * (1 - f))).name()


def theme():
    dark = bool(CFG["dark_mode"])
    t = dict(DARK if dark else LIGHT)
    a1, a2 = ACCENTS.get(CFG["accent"], ACCENTS["Indigo"])
    if dark:
        a1, a2 = QColor(a1).lighter(125).name(), QColor(a2).lighter(115).name()
    t.update(accent=a1, accent2=a2, accent_soft=mix(a1, t["surface"], 0.24 if dark else 0.12))
    t["dark"] = dark
    return t


ICONS = {
    "back": '<path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/>',
    "forward": '<path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>',
    "reload": '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v5h-5"/>',
    "stop": '<path d="M18 6L6 18"/><path d="M6 6l12 12"/>',
    "x": '<path d="M17 7L7 17"/><path d="M7 7l10 10"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "star": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-2.9-5.5 2.9 1-6.2L3 9.6l6.2-.9z"/>',
    "download": '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/>',
    "menu": '<circle cx="12" cy="5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="19" r="1.2"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V7.5a4 4 0 0 1 8 0V11"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "shield_off": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
    "up": '<path d="M18 15l-6-6-6 6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "incognito": '<path d="M3 11h18"/><path d="M6 11l2-6h8l2 6"/><circle cx="7.5" cy="16" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/><path d="M10 16h4"/>',
}

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#6366f1"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs>
<circle cx="32" cy="32" r="30" fill="url(#g)"/>
<path d="M32 11 L37.5 26.5 L53 32 L37.5 37.5 L32 53 L26.5 37.5 L11 32 L26.5 26.5 Z" fill="#ffffff"/>
</svg>"""


def _render_svg(svg, size):
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p)
    p.end()
    return pm


def _icon_svg(name, color, fill="none", width=2):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{fill}" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


_icon_cache = {}


def make_icon(name, color, fill="none"):
    key = (name, color, fill)
    if key not in _icon_cache:
        _icon_cache[key] = QIcon(_render_svg(_icon_svg(name, color, fill), 64))
    return _icon_cache[key]


def logo_icon():
    if "logo" not in _icon_cache:
        _icon_cache["logo"] = QIcon(_render_svg(LOGO_SVG, 128))
    return _icon_cache["logo"]


def write_png(name, color, path, width=2):
    _render_svg(_icon_svg(name, color, width=width), 32).save(str(path), "PNG")


QSS = """
* { font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", sans-serif; font-size: 13px; }
QMainWindow, #central { background: @bg; }
#tabrow { background: @bg; }
#central[private="true"] #tabrow, #central[private="true"] { background: @privbg; }
#privbadge { color: #ffffff; background: #7c3aed; border-radius: 10px; padding: 3px 10px; font-weight: 600; }

QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; color: @muted; padding: 8px 8px 8px 12px; margin: 6px 1px 0 1px;
    border-top-left-radius: 10px; border-top-right-radius: 10px; min-width: 140px; max-width: 230px;
}
QTabBar::tab:hover:!selected { background: @hover; color: @text; }
QTabBar::tab:selected { background: @surface; color: @text; }
QTabBar::close-button { image: url(@closeicon); subcontrol-position: right; border-radius: 5px; padding: 2px; margin-right: 4px; }
QTabBar::close-button:hover { background: @hover; }
QTabBar QToolButton { background: @bg; border: none; border-radius: 6px; }
QTabBar QToolButton:hover { background: @hover; }

#navrow { background: @surface; }
QToolButton#nav { border: none; border-radius: 17px; background: transparent; }
QToolButton#nav:hover { background: @hover; }
QToolButton#nav:pressed { background: @pressed; }
QToolButton#nav::menu-indicator { image: none; width: 0; }
QToolButton#pill { border: 1px solid @border; border-radius: 13px; padding: 3px 10px; color: @text; background: @field; }
QToolButton#pill:hover { background: @hover; }

QLineEdit#urlbar {
    background: @field; color: @text; border: 2px solid transparent; border-radius: 18px;
    padding: 0 8px; min-height: 32px; font-size: 14px; selection-background-color: @accent;
}
QLineEdit#urlbar:hover { background: @hover; }
QLineEdit#urlbar:focus { background: @surface; border: 2px solid @accent; }

#bmbar { background: @surface; border: none; border-bottom: 1px solid @border; padding: 1px 8px 4px 8px; spacing: 2px; }
#bmbar QToolButton { padding: 4px 10px; border-radius: 8px; color: @text; background: transparent; }
#bmbar QToolButton:hover { background: @hover; }

QProgressBar#loadbar { background: @surface; border: none; }
QProgressBar#loadbar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @accent, stop:1 @accent2); }

#banner { background: @accent_soft; border-bottom: 1px solid @border; }
#banner QLabel { color: @text; background: transparent; }

#findbar { background: @surface; border-top: 1px solid @border; }

QPushButton { background: @field; color: @text; border: 1px solid @border; border-radius: 9px; padding: 7px 16px; }
QPushButton:hover { background: @hover; }
QPushButton:pressed { background: @pressed; }
QPushButton#primary { background: @accent; color: #ffffff; border: none; font-weight: 600; }
QPushButton#primary:hover { background: @accent2; }

QMenu { background: @surface; color: @text; border: 1px solid @border; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 34px 8px 14px; border-radius: 7px; }
QMenu::item:selected { background: @hover; }
QMenu::item:disabled { color: @muted; }
QMenu::separator { height: 1px; background: @border; margin: 5px 10px; }

QDialog { background: @surface; }
QLabel { color: @text; }
QLabel#muted { color: @muted; }
QLabel#title { font-size: 18px; font-weight: 600; }
QLineEdit { background: @field; color: @text; border: 1px solid @border; border-radius: 9px; padding: 7px 10px; selection-background-color: @accent; }
QLineEdit:focus { border: 1px solid @accent; }
QComboBox { background: @field; color: @text; border: 1px solid @border; border-radius: 9px; padding: 6px 10px; }
QComboBox:hover { background: @hover; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: @surface; color: @text; border: 1px solid @border; selection-background-color: @accent_soft; selection-color: @text; outline: 0; }
QCheckBox { color: @text; spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 6px; border: 1px solid @border2; background: @field; }
QCheckBox::indicator:hover { border-color: @accent; }
QCheckBox::indicator:checked { background: @accent; border-color: @accent; image: url(@checkicon); }

QListWidget { background: @surface; color: @text; border: 1px solid @border; border-radius: 12px; padding: 5px; outline: 0; }
QListWidget::item { padding: 9px 10px; border-radius: 8px; }
QListWidget::item:hover { background: @hover; }
QListWidget::item:selected { background: @accent_soft; color: @text; }

QProgressBar { background: @field; border: none; border-radius: 4px; max-height: 8px; }
QProgressBar::chunk { background: @accent; border-radius: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @border2; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border2; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: @text; color: @surface; border: none; padding: 6px 9px; border-radius: 7px; }
QLabel#hover { background: @surface; color: @muted; border: 1px solid @border; border-radius: 8px; padding: 4px 10px; font-size: 12px; }
QLabel#toast { background: @text; color: @surface; border-radius: 12px; padding: 10px 18px; font-weight: 500; }
"""


def build_qss(t):
    tokens = dict(t)
    tokens["privbg"] = "#24183f" if t["dark"] else "#e7defc"
    tokens["closeicon"] = (ICON_DIR / ("close_dark.png" if t["dark"] else "close_light.png")).as_posix()
    tokens["checkicon"] = (ICON_DIR / "check_white.png").as_posix()
    qss = QSS
    for k in sorted(tokens, key=len, reverse=True):
        qss = qss.replace("@" + k, str(tokens[k]))
    return qss


def set_dark_titlebar(widget, dark):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(int(widget.winId()), 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def apply_theme():
    app = QApplication.instance()
    t = theme()
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in [(QPalette.ColorRole.Window, "surface"), (QPalette.ColorRole.WindowText, "text"),
                      (QPalette.ColorRole.Base, "field"), (QPalette.ColorRole.AlternateBase, "surface"),
                      (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "field"),
                      (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.ToolTipBase, "text"),
                      (QPalette.ColorRole.ToolTipText, "surface"), (QPalette.ColorRole.Highlight, "accent"),
                      (QPalette.ColorRole.PlaceholderText, "muted")]:
        pal.setColor(role, QColor(t[key]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    write_png("x", LIGHT["muted"], ICON_DIR / "close_light.png")
    write_png("x", DARK["muted"], ICON_DIR / "close_dark.png")
    write_png("check", "#ffffff", ICON_DIR / "check_white.png", width=3)
    app.setStyleSheet(build_qss(t))
    write_newtab()
    for w in WINDOWS:
        w.refresh_icons()
        set_dark_titlebar(w, t["dark"])
    refresh_newtabs()


# ====================================================================== Startseite
NEWTAB_HTML = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Neuer Tab</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font-family:"Segoe UI Variable Display","Segoe UI",Inter,system-ui,sans-serif;color:%%TEXT%%;
 background:radial-gradient(1100px 600px at 15% -10%,%%ACCENT%%2e,transparent 60%),
 radial-gradient(900px 600px at 110% 110%,%%ACCENT2%%26,transparent 60%),%%BG%%;
 display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden}
.wrap{display:flex;flex-direction:column;align-items:center;width:100%;margin-top:-6vh;animation:in .5s ease}
@keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.clock{font-size:88px;font-weight:200;letter-spacing:-2px;line-height:1}
.date{color:%%MUTED%%;font-size:16px;margin-top:10px}
.greet{font-size:22px;font-weight:600;margin:26px 0 22px}
form{width:min(660px,90vw);display:flex;align-items:center;background:%%SURFACE%%;
 border:1px solid %%BORDER%%;border-radius:999px;padding:6px 6px 6px 22px;
 box-shadow:0 12px 40px rgba(0,0,0,%%SHADOW%%);transition:box-shadow .2s,border-color .2s}
form:focus-within{border-color:%%ACCENT%%;box-shadow:0 12px 44px %%ACCENT%%40}
input{flex:1;border:0;background:transparent;font-size:17px;color:%%TEXT%%;outline:none;font-family:inherit}
input::placeholder{color:%%MUTED%%}
button{width:44px;height:44px;border:0;border-radius:50%;cursor:pointer;display:grid;place-items:center;
 background:linear-gradient(135deg,%%ACCENT%%,%%ACCENT2%%);transition:transform .15s}
button:hover{transform:scale(1.06)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,108px);justify-content:center;gap:10px;
 width:min(700px,92vw);margin-top:38px}
.tile{display:flex;flex-direction:column;align-items:center;gap:9px;padding:14px 6px;border-radius:18px;
 text-decoration:none;color:%%TEXT%%;transition:background .15s,transform .15s}
.tile:hover{background:%%SURFACE%%;transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,%%SHADOW%%)}
.ico{width:54px;height:54px;border-radius:50%;background:%%SURFACE%%;border:1px solid %%BORDER%%;
 display:grid;place-items:center;overflow:hidden}
.ico img{width:28px;height:28px}
.ico span{font-size:22px;font-weight:700;color:%%ACCENT%%}
.lbl{font-size:12.5px;color:%%MUTED%%;width:96px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.foot{position:fixed;bottom:14px;font-size:12px;color:%%MUTED%%;opacity:.7}
</style></head><body>
<div class="wrap">
 <div class="clock" id="c">--:--</div>
 <div class="date" id="d"></div>
 <div class="greet" id="g"></div>
 <form id="f" action="%%ACTION%%" method="get">
  <input id="q" name="q" placeholder="Mit %%ENGINE%% suchen oder Adresse eingeben" autocomplete="off">
  <button type="submit" title="Suchen"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff"
   stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg></button>
 </form>
 <div class="tiles">%%TILES%%</div>
</div>
<div class="foot">%%APPFULL%% · Version %%VERSION%%</div>
<script>
function tick(){var n=new Date();
 document.getElementById('c').textContent=n.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'});
 document.getElementById('d').textContent=n.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long'});
 var h=n.getHours();document.getElementById('g').textContent=h<5?'Gute Nacht':h<11?'Guten Morgen':h<18?'Guten Tag':'Guten Abend';}
tick();setInterval(tick,1000);
document.getElementById('f').addEventListener('submit',function(e){
 var v=document.getElementById('q').value.trim();
 if(!v){e.preventDefault();return;}
 if(!/\\s/.test(v)&&(/^https?:\\/\\//i.test(v)||/^[^\\s]+\\.[a-z]{2,}(\\/.*)?$/i.test(v))){
  e.preventDefault();location.href=/^https?:/i.test(v)?v:'https://'+v;}
});
</script></body></html>"""


def write_newtab():
    t = theme()
    eng = SEARCH_ENGINES.get(CFG["search_engine"], SEARCH_ENGINES["DuckDuckGo"])
    tiles = []
    for b in CFG["bookmarks"][:12]:
        url = html.escape(b["url"], quote=True)
        letter = html.escape((b["title"] or "?")[:1].upper(), quote=True)
        fav = "https://www.google.com/s2/favicons?sz=64&domain_url=" + quote_plus(b["url"])
        tiles.append(
            f'<a class="tile" href="{url}"><div class="ico"><img src="{fav}" data-l="{letter}" '
            f'onerror="var s=document.createElement(\'span\');s.textContent=this.dataset.l;this.replaceWith(s)">'
            f'</div><span class="lbl">{html.escape(b["title"])}</span></a>')
    page = NEWTAB_HTML
    repl = {"TEXT": t["text"], "MUTED": t["muted"], "BG": t["bg"], "SURFACE": t["surface"],
            "BORDER": t["border"], "ACCENT2": t["accent2"], "ACCENT": t["accent"],
            "SHADOW": ".35" if t["dark"] else ".07", "ACTION": eng.split("?")[0],
            "ENGINE": CFG["search_engine"], "TILES": "".join(tiles), "VERSION": VERSION, "APPFULL": APP_FULL}
    for k, v in repl.items():
        page = page.replace(f"%%{k}%%", v)
    try:
        NEWTAB_FILE.write_text(page, encoding="utf-8")
    except Exception:
        pass


def refresh_newtabs():
    for w in WINDOWS:
        for i in range(w.tabs.count()):
            v = w.tabs.widget(i)
            if is_newtab(v.url()):
                v.reload()


# ====================================================================== Updater
def version_tuple(v):
    nums = re.findall(r"\d+", str(v))
    return tuple(int(n) for n in nums[:4]) or (0,)


def source_version(src):
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else "0"


class Updater(QObject):
    """Lokale Updates (Datei ändert sich) und Online-Updates (UPDATE_URL)."""

    def __init__(self):
        super().__init__()
        self.shown_hash = START_HASH
        self.paths = [APP_FILE]
        local = os.environ.get("NYROX_LOCAL_SOURCE")
        if local and Path(local).resolve() != APP_FILE and Path(local).exists():
            self.paths.append(Path(local).resolve())
        self.watcher = QFileSystemWatcher(self)
        for p in self.paths:
            self.watcher.addPath(str(p))
        self.watcher.fileChanged.connect(lambda _p: self.debounce.start())
        self.debounce = QTimer(self, singleShot=True, interval=1500)
        self.debounce.timeout.connect(lambda: self.check(False))
        self.poll = QTimer(self, interval=60_000)      # Sicherheitsnetz, falls Dateiüberwachung ausfällt
        self.poll.timeout.connect(lambda: self.check(False))
        self.poll.start()
        self.net = QNetworkAccessManager(self)
        self.online_timer = QTimer(self, interval=UPDATE_INTERVAL_MIN * 60_000)
        self.online_timer.timeout.connect(lambda: self.check_online(False))
        if UPDATE_URL:
            self.online_timer.start()
            QTimer.singleShot(5000, lambda: self.check_online(False))

    # ---------- lokal
    def check(self, manual=False):
        for p in self.paths:
            if p.exists() and str(p) not in self.watcher.files():
                self.watcher.addPath(str(p))
        for p in self.paths:
            try:
                raw = p.read_bytes()
                src = raw.decode("utf-8")
                compile(src, str(p), "exec")      # nur fehlerfreie Updates anbieten
            except Exception as e:
                if manual and p == APP_FILE:
                    toast_all(f"Update-Datei ist fehlerhaft: {e.__class__.__name__}")
                continue
            h = hashlib.sha1(raw).hexdigest()
            ver = source_version(src)
            changed = (h != START_HASH) if p == APP_FILE else version_tuple(ver) > version_tuple(VERSION)
            if changed and (h != self.shown_hash or manual):
                self.shown_hash = h
                self.offer(ver)
                return
        if manual:
            toast_all(f"Du hast die neueste Version ({VERSION}).")

    # ---------- online
    def check_online(self, manual=False):
        if not UPDATE_URL:
            if manual:
                self.check(True)
            return
        sep = "&" if "?" in UPDATE_URL else "?"
        req = QNetworkRequest(QUrl(f"{UPDATE_URL}{sep}t={int(time.time())}"))
        req.setRawHeader(b"Cache-Control", b"no-cache")
        req.setTransferTimeout(20_000)
        reply = self.net.get(req)
        reply.finished.connect(lambda r=reply: self._online_done(r, manual))
        if manual:
            toast_all("Suche nach Updates …")

    def _online_done(self, reply, manual):
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if manual:
                    toast_all("Keine Verbindung zum Update-Server.")
                return
            raw = bytes(reply.readAll())
            src = raw.decode("utf-8")
            compile(src, "browser.py", "exec")
            ver = source_version(src)
            if version_tuple(ver) <= version_tuple(VERSION) or "class BrowserWindow" not in src:
                if manual:
                    toast_all(f"Du hast die neueste Version ({VERSION}).")
                return
            target = UPDATE_DIR / "browser.py"
            tmp = UPDATE_DIR / "browser.py.download"
            tmp.write_bytes(raw)
            os.replace(tmp, target)
            self.shown_hash = hashlib.sha1(raw).hexdigest()
            self.offer(ver)
        except Exception as e:
            if manual:
                toast_all(f"Update fehlgeschlagen: {e.__class__.__name__}")
        finally:
            reply.deleteLater()

    def offer(self, ver):
        for w in WINDOWS:
            w.show_banner(f"Update verfügbar – Version {ver}. Neu starten, um es zu installieren.",
                          "Jetzt neu starten", restart_app, "sparkle")


RESTARTING = False


def restart_app():
    global RESTARTING
    save_all_sessions()
    RESTARTING = True
    CFG.data["restore_once"] = True
    CFG.data["running"] = False
    CFG.save()
    if getattr(sys, "frozen", False):
        QProcess.startDetached(sys.executable, [])
    else:
        QProcess.startDetached(sys.executable, [str(APP_FILE)])
    QApplication.quit()


def save_all_sessions():
    urls = []
    for w in WINDOWS:
        if w.private:
            continue
        for i in range(w.tabs.count()):
            u = w.tabs.widget(i).url()
            if u.isValid() and not u.isEmpty() and not is_newtab(u):
                urls.append(u.toString())
    CFG["session"] = urls


_session_timer = None


def schedule_session_save():
    """Sichert die offenen Tabs kurz nach jedem Seitenwechsel (für die Wiederherstellung nach Abstürzen)."""
    global _session_timer
    if _session_timer is None:
        _session_timer = QTimer(singleShot=True, interval=2000)
        _session_timer.timeout.connect(save_all_sessions)
    _session_timer.start()


def on_quit():
    if RESTARTING:
        return
    save_all_sessions()
    CFG.data["running"] = False
    CFG.save()


def toast_all(msg):
    for w in WINDOWS:
        w.toast(msg)


def show_changelog(parent=None):
    parts = []
    for ver, items in CHANGELOG.items():
        parts.append(f"<h3 style='margin-bottom:4px'>Version {ver}</h3><ul>"
                     + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>")
    box = QMessageBox(parent)
    box.setWindowTitle("Neuigkeiten")
    box.setIconPixmap(logo_icon().pixmap(56, 56))
    box.setText("".join(parts))
    box.exec()


# ====================================================================== Werbeblocker
class AdBlocker(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        if not CFG["adblock"]:
            return
        host = info.requestUrl().host().lower()
        for ad in AD_HOSTS:
            if host == ad or host.endswith("." + ad):
                info.block(True)
                return


# ====================================================================== Webseite
class WebPage(QWebEnginePage):
    def __init__(self, profile, window):
        super().__init__(profile, window)
        self.window_ref = window
        if hasattr(self, "permissionRequested"):          # Qt >= 6.8
            self.permissionRequested.connect(self.on_permission_new)
        else:
            self.featurePermissionRequested.connect(self.on_permission)
        self.certificateError.connect(self.on_certificate_error)

    def createWindow(self, _type):
        if CFG["block_popups"] and _type == QWebEnginePage.WebWindowType.WebBrowserWindow:
            self.window_ref.toast("Pop-up blockiert")
            return None
        bg = _type == QWebEnginePage.WebWindowType.WebBrowserBackgroundTab
        return self.window_ref.add_tab(background=bg, load=False).page()

    def _ask(self, origin, what):
        return QMessageBox.question(self.window_ref, "Berechtigung",
                                    f"{origin} möchte Zugriff auf: {what}\n\nErlauben?") == QMessageBox.StandardButton.Yes

    def on_permission(self, origin, feature):
        F = QWebEnginePage.Feature
        names = {F.Geolocation: "Standort", F.MediaAudioCapture: "Mikrofon", F.MediaVideoCapture: "Kamera",
                 F.MediaAudioVideoCapture: "Kamera & Mikrofon", F.Notifications: "Benachrichtigungen",
                 F.DesktopVideoCapture: "Bildschirmfreigabe", F.DesktopAudioVideoCapture: "Bildschirm & Ton"}
        ok = self._ask(origin.host(), names.get(feature, "eine Funktion"))
        P = QWebEnginePage.PermissionPolicy
        self.setFeaturePermission(origin, feature, P.PermissionGrantedByUser if ok else P.PermissionDeniedByUser)

    def on_permission_new(self, permission):
        try:
            names = {"Geolocation": "Standort", "MediaAudioCapture": "Mikrofon", "MediaVideoCapture": "Kamera",
                     "MediaAudioVideoCapture": "Kamera & Mikrofon", "Notifications": "Benachrichtigungen",
                     "DesktopVideoCapture": "Bildschirmfreigabe", "DesktopAudioVideoCapture": "Bildschirm & Ton",
                     "ClipboardReadWrite": "Zwischenablage"}
            kind = getattr(permission.permissionType(), "name", str(permission.permissionType()))
            ok = self._ask(permission.origin().host(), names.get(kind, kind))
            permission.grant() if ok else permission.deny()
        except Exception:
            pass

    def on_certificate_error(self, error):
        ok = QMessageBox.warning(
            self.window_ref, "Zertifikatsfehler",
            f"Die Verbindung zu {error.url().host()} ist nicht sicher:\n{error.description()}\n\nTrotzdem fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
        try:
            error.acceptCertificate() if ok else error.rejectCertificate()
        except Exception:
            pass


class WebView(QWebEngineView):
    def __init__(self, window):
        super().__init__()
        self.window_ref = window
        self.setPage(WebPage(window.profile, window))

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        req = self.lastContextMenuRequest()
        extra = []
        if req is not None and req.linkUrl().isValid():
            link = QUrl(req.linkUrl())
            extra = [("Link in neuem Tab öffnen", lambda: self.window_ref.add_tab(link, background=True)),
                     ("Link in privatem Fenster öffnen", lambda: open_private(link))]
        first = menu.actions()[0] if menu.actions() else None
        for text, fn in extra:
            a = QAction(text, menu)
            a.triggered.connect(fn)
            if first:
                menu.insertAction(first, a)
            else:
                menu.addAction(a)
        if extra and first:
            menu.insertSeparator(first)
        menu.addSeparator()
        for text, fn in (("Seitenquelltext anzeigen", self.window_ref.view_source),
                         ("Untersuchen", self.window_ref.toggle_devtools)):
            a = QAction(text, menu)
            a.triggered.connect(fn)
            menu.addAction(a)
        menu.exec(event.globalPos())


# ====================================================================== Tab-Verwaltung
class Tabs(QObject):
    """Verbindet eine Tab-Leiste (oben) mit dem Seitenstapel (unten)."""
    currentChanged = pyqtSignal(int)

    def __init__(self, bar: QTabBar, stack: QStackedWidget):
        super().__init__(bar)
        self.bar, self.stack = bar, stack
        bar.currentChanged.connect(self._on_current)
        bar.tabMoved.connect(self._on_moved)

    def _on_current(self, i):
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
        self.currentChanged.emit(i)

    def _on_moved(self, frm, to):
        w = self.stack.widget(frm)
        self.stack.removeWidget(w)
        self.stack.insertWidget(to, w)
        self.stack.setCurrentIndex(self.bar.currentIndex())

    def addTab(self, w, title):
        self.stack.addWidget(w)
        return self.bar.addTab(title)

    def removeTab(self, i):
        w = self.stack.widget(i)
        self.stack.removeWidget(w)
        self.bar.removeTab(i)
        if self.bar.currentIndex() >= 0:
            self.stack.setCurrentIndex(self.bar.currentIndex())

    def widget(self, i): return self.stack.widget(i)
    def indexOf(self, w): return self.stack.indexOf(w)
    def count(self): return self.bar.count()
    def currentIndex(self): return self.bar.currentIndex()
    def setCurrentIndex(self, i): self.bar.setCurrentIndex(i)
    def currentWidget(self): return self.stack.widget(self.bar.currentIndex())
    def setTabText(self, i, t): self.bar.setTabText(i, t)
    def setTabIcon(self, i, ic): self.bar.setTabIcon(i, ic)
    def setTabToolTip(self, i, t): self.bar.setTabToolTip(i, t)
    def tabBar(self): return self.bar


# ====================================================================== Dialoge
class HistoryDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Verlauf")
        self.resize(760, 540)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Verlauf", objectName="title"))
        self.search = QLineEdit(placeholderText="Verlauf durchsuchen …")
        self.search.textChanged.connect(self.fill)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_item)
        btns = QHBoxLayout()
        delete = QPushButton("Eintrag löschen")
        delete.clicked.connect(self.delete)
        clear = QPushButton("Browserdaten löschen …")
        clear.clicked.connect(self.clear)
        btns.addWidget(delete)
        btns.addStretch()
        btns.addWidget(clear)
        lay.addWidget(self.search)
        lay.addWidget(self.list)
        lay.addLayout(btns)
        self.fill()

    def open_item(self, it):
        self.window_ref.add_tab(QUrl(it.data(Qt.ItemDataRole.UserRole)))
        self.close()

    def fill(self):
        self.list.clear()
        q = self.search.text().lower()
        hist = CFG["history"]
        for idx in range(len(hist) - 1, -1, -1):
            h = hist[idx]
            if q and q not in h.get("title", "").lower() and q not in h["url"].lower():
                continue
            it = QListWidgetItem(f"{h.get('title') or h['url']}\n{h.get('time', '')}  ·  {h['url']}")
            it.setData(Qt.ItemDataRole.UserRole, h["url"])
            it.setData(Qt.ItemDataRole.UserRole + 1, idx)
            self.list.addItem(it)
            if self.list.count() >= 1500:
                break

    def delete(self):
        it = self.list.currentItem()
        if it:
            del CFG.data["history"][it.data(Qt.ItemDataRole.UserRole + 1)]
            CFG.save()
            self.fill()

    def clear(self):
        if QMessageBox.question(self, "Browserdaten löschen",
                                "Verlauf, Cache und Cookies vollständig löschen?") == QMessageBox.StandardButton.Yes:
            CFG["history"] = []
            self.window_ref.profile.clearHttpCache()
            self.window_ref.profile.cookieStore().deleteAllCookies()
            self.fill()
            self.window_ref.toast("Browserdaten gelöscht")


class BookmarksDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Lesezeichen")
        self.resize(660, 480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Lesezeichen", objectName="title"))
        lay.addWidget(QLabel("Ziehen zum Sortieren · Doppelklick zum Öffnen", objectName="muted"))
        self.list = QListWidget()
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.itemDoubleClicked.connect(self.open_item)
        btns = QHBoxLayout()
        for text, fn in [("Umbenennen", self.rename), ("Löschen", self.delete),
                         ("Exportieren", self.export), ("Importieren", self.import_)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        lay.addWidget(self.list)
        lay.addLayout(btns)
        self.fill()

    def open_item(self, it):
        self.window_ref.add_tab(QUrl(it.data(Qt.ItemDataRole.UserRole)["url"]))
        self.close()

    def fill(self):
        self.list.clear()
        for b in CFG["bookmarks"]:
            it = QListWidgetItem(f"{b['title']}\n{b['url']}")
            it.setData(Qt.ItemDataRole.UserRole, b)
            self.list.addItem(it)

    def _store(self):
        CFG["bookmarks"] = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
        bookmarks_changed()

    def rename(self):
        it = self.list.currentItem()
        if not it:
            return
        b = dict(it.data(Qt.ItemDataRole.UserRole))
        t, ok = QInputDialog.getText(self, "Umbenennen", "Titel:", text=b["title"])
        if ok and t:
            b["title"] = t
            it.setData(Qt.ItemDataRole.UserRole, b)
            self._store()
            self.fill()

    def delete(self):
        it = self.list.currentItem()
        if it:
            self.list.takeItem(self.list.row(it))
            self._store()

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Exportieren", "lesezeichen.json", "JSON (*.json)")
        if p:
            Path(p).write_text(json.dumps(CFG["bookmarks"], ensure_ascii=False, indent=1), encoding="utf-8")

    def import_(self):
        p, _ = QFileDialog.getOpenFileName(self, "Importieren", "", "JSON (*.json)")
        if p:
            try:
                CFG["bookmarks"] = CFG["bookmarks"] + json.loads(Path(p).read_text(encoding="utf-8"))
                self.fill()
                bookmarks_changed()
            except Exception as e:
                QMessageBox.warning(self, "Fehler", str(e))

    def closeEvent(self, e):
        self._store()
        super().closeEvent(e)


def bookmarks_changed():
    for w in WINDOWS:
        w.refresh_bookmark_bar()
    write_newtab()
    refresh_newtabs()


class DownloadItem(QWidget):
    def __init__(self, dl: QWebEngineDownloadRequest):
        super().__init__()
        self.dl = dl
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        col = QVBoxLayout()
        self.name = QLabel(dl.downloadFileName())
        self.info = QLabel("", objectName="muted")
        self.bar = QProgressBar(textVisible=False)
        self.bar.setRange(0, 100)
        col.addWidget(self.name)
        col.addWidget(self.bar)
        col.addWidget(self.info)
        self.btn = QPushButton("Abbrechen")
        self.btn.clicked.connect(self.action)
        lay.addLayout(col, 1)
        lay.addWidget(self.btn)
        dl.receivedBytesChanged.connect(self.update_state)
        dl.stateChanged.connect(self.update_state)
        self.update_state()

    def update_state(self):
        tot, rec = self.dl.totalBytes(), self.dl.receivedBytes()
        self.bar.setValue(int(rec * 100 / tot) if tot > 0 else 0)
        S = QWebEngineDownloadRequest.DownloadState
        st = self.dl.state()
        mb = lambda b: f"{b / 1048576:.1f} MB"
        status = f"{mb(rec)} von {mb(tot) if tot > 0 else '?'}"
        if st == S.DownloadCompleted:
            self.btn.setText("Ordner öffnen")
            self.btn.setObjectName("primary")
            self.btn.style().unpolish(self.btn)
            self.btn.style().polish(self.btn)
            self.bar.setValue(100)
            status = f"Fertig · {mb(tot if tot > 0 else rec)}"
        elif st == S.DownloadCancelled:
            self.btn.setEnabled(False)
            status = "Abgebrochen"
        elif st == S.DownloadInterrupted:
            self.btn.setEnabled(False)
            status = "Unterbrochen"
        self.info.setText(status)

    def action(self):
        if self.dl.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.dl.downloadDirectory()))
        else:
            self.dl.cancel()


class DownloadsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Downloads")
        self.setWindowIcon(logo_icon())
        self.resize(620, 400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Downloads", objectName="title"))
        self.list = QListWidget()
        lay.addWidget(self.list)

    def add(self, dl):
        it = QListWidgetItem()
        w = DownloadItem(dl)
        it.setSizeHint(w.sizeHint())
        self.list.insertItem(0, it)
        self.list.setItemWidget(it, w)


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("Einstellungen")
        self.resize(520, 0)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(QLabel("Einstellungen", objectName="title"))
        f = QFormLayout()
        f.setVerticalSpacing(10)
        f.setHorizontalSpacing(14)
        self.home = QLineEdit(CFG["homepage"], placeholderText="leer = NyroxNite-Startseite")
        self.engine = QComboBox()
        self.engine.addItems(SEARCH_ENGINES)
        self.engine.setCurrentText(CFG["search_engine"])
        self.accent = QComboBox()
        self.accent.addItems(ACCENTS)
        self.accent.setCurrentText(CFG["accent"])
        self.dark = QCheckBox("Dunkles Design")
        self.dark.setChecked(CFG["dark_mode"])
        self.darkweb = QCheckBox("Webseiten ebenfalls dunkel darstellen")
        self.darkweb.setChecked(CFG["force_dark_web"])
        self.ad = QCheckBox("Werbung blockieren")
        self.ad.setChecked(CFG["adblock"])
        self.pop = QCheckBox("Pop-up-Fenster blockieren")
        self.pop.setChecked(CFG["block_popups"])
        self.js = QCheckBox("JavaScript aktivieren")
        self.js.setChecked(CFG["javascript"])
        self.sess = QCheckBox("Letzte Sitzung beim Start wiederherstellen")
        self.sess.setChecked(CFG["restore_session"])
        self.gpu = QCheckBox("Hardwarebeschleunigung verwenden (aus = stabiler, Neustart nötig)")
        self.gpu.setChecked(CFG["hardware_accel"])
        dlrow = QHBoxLayout()
        self.dldir = QLineEdit(CFG["download_dir"])
        pick = QPushButton("Ändern")
        pick.clicked.connect(self.pick_dir)
        dlrow.addWidget(self.dldir)
        dlrow.addWidget(pick)
        f.addRow("Startseite", self.home)
        f.addRow("Suchmaschine", self.engine)
        f.addRow("Akzentfarbe", self.accent)
        f.addRow("Downloads", dlrow)
        outer.addLayout(f)
        for w in (self.dark, self.darkweb, self.ad, self.pop, self.js, self.sess, self.gpu):
            outer.addWidget(w)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Download-Ordner", self.dldir.text())
        if d:
            self.dldir.setText(d)

    def save(self):
        CFG.data.update(homepage=self.home.text().strip(), search_engine=self.engine.currentText(),
                        accent=self.accent.currentText(), dark_mode=self.dark.isChecked(),
                        force_dark_web=self.darkweb.isChecked(), adblock=self.ad.isChecked(),
                        block_popups=self.pop.isChecked(), javascript=self.js.isChecked(),
                        restore_session=self.sess.isChecked(), download_dir=self.dldir.text())
        gpu_changed = self.gpu.isChecked() != bool(CFG["hardware_accel"])
        CFG.data["hardware_accel"] = self.gpu.isChecked()
        CFG.save()
        if gpu_changed:
            for w in WINDOWS:
                w.show_banner("Die Grafikeinstellung wird nach einem Neustart aktiv.", "Jetzt neu starten",
                              restart_app, "sparkle")
        apply_theme()
        for w in WINDOWS:
            w.apply_web_settings()
        self.accept()


# ====================================================================== Profile & Downloads
def get_profile(private):
    key = "private" if private else "default"
    if key not in _profiles:
        if private:
            p = QWebEngineProfile()  # Off-the-record: nichts wird gespeichert
        else:
            p = QWebEngineProfile("Standard")
            p.setPersistentStoragePath(str(DATA_DIR / "storage"))
            p.setCachePath(str(DATA_DIR / "cache"))
            p.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        p._blocker = AdBlocker()
        p.setUrlRequestInterceptor(p._blocker)
        p.downloadRequested.connect(on_download)
        _profiles[key] = p
    return _profiles[key]


def on_download(dl: QWebEngineDownloadRequest):
    path, _ = QFileDialog.getSaveFileName(None, "Datei speichern",
                                          os.path.join(CFG["download_dir"], dl.downloadFileName()))
    if not path:
        dl.cancel()
        return
    dl.setDownloadDirectory(os.path.dirname(path))
    dl.setDownloadFileName(os.path.basename(path))
    dl.accept()
    DOWNLOADS.add(dl)
    DOWNLOADS.show()
    DOWNLOADS.raise_()


def open_private(url=None):
    w = BrowserWindow(private=True)
    w.add_tab(url)
    w.show()


def new_window(urls=None):
    w = BrowserWindow()
    if urls:
        for u in urls:
            w.add_tab(QUrl.fromUserInput(u) if isinstance(u, str) else u, background=True)
        w.tabs.setCurrentIndex(0)
    else:
        w.add_tab(home_url())
    w.update_completer()
    w.show()
    return w


# ====================================================================== Hauptfenster
class BrowserWindow(QMainWindow):
    def __init__(self, private=False):
        super().__init__()
        WINDOWS.append(self)
        self.private = private
        self.profile = get_profile(private)
        self.closed_tabs = []
        self.devtools = None
        self.icon_buttons = {}
        self.banner_action = None
        self.loading = False
        self.setWindowTitle(APP_FULL + (" – Privat" if private else ""))
        self.setWindowIcon(logo_icon())
        self.resize(1320, 860)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        central = QWidget(objectName="central")
        central.setProperty("private", "true" if private else "false")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.build_tabrow(root)
        self.build_navrow(root)
        self.build_bookmark_bar(root)

        self.loadbar = QProgressBar(objectName="loadbar", textVisible=False)
        self.loadbar.setRange(0, 100)
        self.loadbar.setValue(0)
        self.loadbar.setFixedHeight(2)
        root.addWidget(self.loadbar)

        self.build_banner(root)
        root.addWidget(self.stack, 1)
        self.build_find_bar(root)

        self.hover = QLabel(self.stack, objectName="hover")
        self.hover.hide()
        self.toast_lbl = QLabel(self.stack, objectName="toast")
        self.toast_lbl.hide()
        self.toast_timer = QTimer(self, singleShot=True, interval=2800)
        self.toast_timer.timeout.connect(self.toast_lbl.hide)

        self.build_menu()
        self.build_shortcuts()
        self.refresh_icons()
        if private:
            self.toast("Privates Fenster – Verlauf, Cookies und Cache werden nicht gespeichert.")

    # ------------------------------------------------------------ Aufbau
    def icon_button(self, name, tip, fn):
        b = QToolButton(objectName="nav")
        b.setToolTip(tip)
        b.setIconSize(QSize(18, 18))
        b.setFixedSize(34, 34)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if fn:
            b.clicked.connect(fn)
        self.icon_buttons[b] = name
        return b

    def build_tabrow(self, root):
        self.tabrow = QWidget(objectName="tabrow")
        self.tabrow.installEventFilter(self)
        tr = QHBoxLayout(self.tabrow)
        tr.setContentsMargins(8, 0, 8, 0)
        tr.setSpacing(4)
        bar = QTabBar(objectName="tabs")
        bar.setTabsClosable(True)
        bar.setMovable(True)
        bar.setExpanding(False)
        bar.setDocumentMode(True)
        bar.setDrawBase(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        bar.setIconSize(QSize(16, 16))
        bar.tabCloseRequested.connect(self.close_tab)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self.tab_menu)
        bar.installEventFilter(self)
        self.stack = QStackedWidget()
        self.tabs = Tabs(bar, self.stack)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        tr.addWidget(bar, 0, Qt.AlignmentFlag.AlignBottom)
        self.newtab_btn = self.icon_button("plus", "Neuer Tab (Strg+T)", lambda: self.add_tab())
        self.newtab_btn.setFixedSize(30, 30)
        tr.addWidget(self.newtab_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        tr.addStretch(1)
        if self.private:
            tr.addWidget(QLabel("Privat", objectName="privbadge"), 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.tabrow)

    def build_navrow(self, root):
        self.navrow = QWidget(objectName="navrow")
        nr = QHBoxLayout(self.navrow)
        nr.setContentsMargins(8, 6, 8, 6)
        nr.setSpacing(2)
        self.back_btn = self.icon_button("back", "Zurück (Alt+←)", lambda: self.view().back())
        self.fwd_btn = self.icon_button("forward", "Vor (Alt+→)", lambda: self.view().forward())
        self.reload_btn = self.icon_button("reload", "Neu laden (F5)", self.reload_or_stop)
        self.home_btn = self.icon_button("home", "Startseite (Alt+Pos1)", self.go_home)
        for b in (self.back_btn, self.fwd_btn, self.reload_btn, self.home_btn):
            nr.addWidget(b)
        nr.addSpacing(6)

        self.urlbar = QLineEdit(objectName="urlbar", placeholderText="Suchen oder Adresse eingeben")
        self.urlbar.returnPressed.connect(self.navigate)
        self.url_icon = self.urlbar.addAction(QIcon(), QLineEdit.ActionPosition.LeadingPosition)
        self.star_act = self.urlbar.addAction(QIcon(), QLineEdit.ActionPosition.TrailingPosition)
        self.star_act.setToolTip("Lesezeichen (Strg+D)")
        self.star_act.triggered.connect(self.toggle_bookmark)
        self.completer_model = QStringListModel()
        comp = QCompleter(self.completer_model, self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setMaxVisibleItems(8)
        comp.activated.connect(self.on_completion)
        self.urlbar.setCompleter(comp)
        nr.addWidget(self.urlbar, 1)
        nr.addSpacing(6)

        self.zoom_btn = QToolButton(objectName="pill")
        self.zoom_btn.setToolTip("Zoom zurücksetzen")
        self.zoom_btn.clicked.connect(lambda: self.zoom(0))
        self.zoom_btn.hide()
        nr.addWidget(self.zoom_btn)
        self.shield_btn = self.icon_button("shield", "Werbeblocker an/aus", self.toggle_adblock)
        self.dl_btn = self.icon_button("download", "Downloads (Strg+J)", show_downloads)
        self.theme_btn = self.icon_button("moon", "Hell/Dunkel umschalten", self.toggle_theme)
        self.menu_btn = self.icon_button("menu", "Menü", None)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        for b in (self.shield_btn, self.dl_btn, self.theme_btn, self.menu_btn):
            nr.addWidget(b)
        root.addWidget(self.navrow)

    def build_bookmark_bar(self, root):
        self.bm_bar = QToolBar("Lesezeichen", objectName="bmbar")
        self.bm_bar.setMovable(False)
        self.bm_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        root.addWidget(self.bm_bar)
        self.bm_bar.setVisible(bool(CFG["show_bookmarks"]))
        self.refresh_bookmark_bar()

    def refresh_bookmark_bar(self):
        self.bm_bar.clear()
        for b in CFG["bookmarks"]:
            title = b["title"] if len(b["title"]) <= 24 else b["title"][:23] + "…"
            a = QAction(title, self)
            a.setToolTip(b["url"])
            a.triggered.connect(lambda _=False, u=b["url"]: self.view().setUrl(QUrl(u)))
            self.bm_bar.addAction(a)
        if not CFG["bookmarks"]:
            a = QAction("Lesezeichen mit Strg+D hinzufügen", self)
            a.setEnabled(False)
            self.bm_bar.addAction(a)
        self.update_star()

    def toggle_bookmark_bar(self):
        CFG["show_bookmarks"] = not CFG["show_bookmarks"]
        for w in WINDOWS:
            w.bm_bar.setVisible(bool(CFG["show_bookmarks"]))

    def build_banner(self, root):
        self.banner = QFrame(objectName="banner")
        hl = QHBoxLayout(self.banner)
        hl.setContentsMargins(14, 8, 10, 8)
        hl.setSpacing(10)
        self.banner_icon = QLabel()
        self.banner_text = QLabel()
        self.banner_btn = QPushButton(objectName="primary")
        self.banner_btn.clicked.connect(self._banner_clicked)
        later = QPushButton("Später")
        later.clicked.connect(self.banner.hide)
        hl.addWidget(self.banner_icon)
        hl.addWidget(self.banner_text, 1)
        hl.addWidget(self.banner_btn)
        hl.addWidget(later)
        self.banner.hide()
        root.addWidget(self.banner)

    def show_banner(self, text, button, action, icon="sparkle"):
        self.banner_icon.setPixmap(make_icon(icon, theme()["accent"]).pixmap(20, 20))
        self.banner_text.setText(text)
        self.banner_btn.setText(button)
        self.banner_action = action
        self.banner.show()

    def _banner_clicked(self):
        self.banner.hide()
        if self.banner_action:
            self.banner_action()

    def build_find_bar(self, root):
        self.find_bar = QWidget(objectName="findbar")
        fl = QHBoxLayout(self.find_bar)
        fl.setContentsMargins(10, 6, 10, 6)
        fl.setSpacing(6)
        self.find_input = QLineEdit(placeholderText="Auf Seite suchen …")
        self.find_input.setMaximumWidth(320)
        self.find_input.textChanged.connect(lambda: self.find(False))
        self.find_input.returnPressed.connect(lambda: self.find(False))
        self.find_case = QCheckBox("Groß-/Kleinschreibung")
        self.find_count = QLabel("", objectName="muted")
        up = self.icon_button("up", "Vorheriger Treffer", lambda: self.find(True))
        down = self.icon_button("down", "Nächster Treffer", lambda: self.find(False))
        close = self.icon_button("x", "Schließen (Esc)", self.hide_find)
        for w in (self.find_input, up, down, self.find_case, self.find_count):
            fl.addWidget(w)
        fl.addStretch(1)
        fl.addWidget(close)
        self.find_bar.hide()
        root.addWidget(self.find_bar)

    def build_menu(self):
        m = QMenu(self)
        items = [
            ("Neuer Tab", "Ctrl+T", lambda: self.add_tab()),
            ("Neues Fenster", "Ctrl+N", lambda: new_window()),
            ("Neues privates Fenster", "Ctrl+Shift+N", lambda: open_private()),
            None,
            ("Verlauf", "Ctrl+H", lambda: HistoryDialog(self).exec()),
            ("Lesezeichen verwalten", "Ctrl+Shift+O", lambda: BookmarksDialog(self).exec()),
            ("Lesezeichenleiste ein/aus", "Ctrl+Shift+B", self.toggle_bookmark_bar),
            ("Downloads", "Ctrl+J", show_downloads),
            ("Geschlossenen Tab wiederherstellen", "Ctrl+Shift+T", self.reopen_tab),
            None,
            ("Vergrößern", "Ctrl++", lambda: self.zoom(0.1)),
            ("Verkleinern", "Ctrl+-", lambda: self.zoom(-0.1)),
            ("Zoom zurücksetzen", "Ctrl+0", lambda: self.zoom(0)),
            ("Vollbild", "F11", self.toggle_fullscreen),
            None,
            ("Auf Seite suchen", "Ctrl+F", self.show_find),
            ("Seite speichern …", "Ctrl+S", self.save_page),
            ("Als PDF speichern …", "Ctrl+Shift+P", self.save_pdf),
            ("Drucken …", "Ctrl+P", self.print_page),
            ("Seitenquelltext", "Ctrl+U", self.view_source),
            ("Entwicklertools", "F12", self.toggle_devtools),
            None,
            ("Einstellungen", "Ctrl+,", lambda: SettingsDialog(self).exec()),
            ("Nach Updates suchen", None, lambda: UPDATER and UPDATER.check_online(True)),
            ("Neuigkeiten", None, lambda: show_changelog(self)),
            ("Über NyroxNite", None, self.about),
            ("Beenden", "Ctrl+Q", QApplication.quit),
        ]
        for it in items:
            if it is None:
                m.addSeparator()
                continue
            text, sc, fn = it
            a = QAction(text, self)
            if sc:
                a.setShortcut(QKeySequence(sc))
                a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            a.triggered.connect(fn)
            m.addAction(a)
            self.addAction(a)
        self.menu_btn.setMenu(m)

    def build_shortcuts(self):
        sc = [
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+L", self.focus_urlbar),
            ("F6", self.focus_urlbar),
            ("Alt+D", self.focus_urlbar),
            ("F5", lambda: self.view().reload()),
            ("Ctrl+R", lambda: self.view().reload()),
            ("Ctrl+F5", lambda: self.view().triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)),
            ("Alt+Left", lambda: self.view().back()),
            ("Alt+Right", lambda: self.view().forward()),
            ("Alt+Home", self.go_home),
            ("Ctrl+D", self.toggle_bookmark),
            ("Ctrl+Tab", lambda: self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())),
            ("Ctrl+Shift+Tab", lambda: self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % self.tabs.count())),
            ("Ctrl+=", lambda: self.zoom(0.1)),
        ]
        for i in range(1, 10):
            sc.append((f"Ctrl+{i}", lambda i=i: self.tabs.setCurrentIndex(self.tabs.count() - 1 if i == 9 else i - 1)))
        for key, fn in sc:
            QShortcut(QKeySequence(key), self, activated=fn)
        self.esc = QShortcut(QKeySequence("Escape"), self, activated=self.on_escape)
        self.esc.setEnabled(False)

    def update_esc(self):
        self.esc.setEnabled(self.find_bar.isVisible() or self.isFullScreen())

    def eventFilter(self, obj, ev):
        tabs = getattr(self, "tabs", None)
        if tabs is not None and obj is tabs.tabBar() and ev.type() == QEvent.Type.MouseButtonRelease \
                and ev.button() == Qt.MouseButton.MiddleButton:
            i = obj.tabAt(ev.position().toPoint())
            if i >= 0:
                self.close_tab(i)
                return True
        if obj is getattr(self, "tabrow", None) and ev.type() == QEvent.Type.MouseButtonDblClick:
            self.add_tab()
            return True
        return super().eventFilter(obj, ev)

    # ------------------------------------------------------------ Symbole
    def refresh_icons(self):
        t = theme()
        for b, name in self.icon_buttons.items():
            if b is self.reload_btn:
                name = "stop" if self.loading else "reload"
            elif b is self.theme_btn:
                name = "sun" if t["dark"] else "moon"
            elif b is self.shield_btn:
                b.setIcon(make_icon("shield" if CFG["adblock"] else "shield_off",
                                    t["accent"] if CFG["adblock"] else t["muted"]))
                b.setToolTip("Werbeblocker: an" if CFG["adblock"] else "Werbeblocker: aus")
                continue
            b.setIcon(make_icon(name, t["text"]))
        self.update_star()
        v = self.view()
        if v:
            self.update_url_icon(v.url())

    def update_url_icon(self, url):
        t = theme()
        if is_newtab(url) or url.isEmpty():
            self.url_icon.setIcon(make_icon("search", t["muted"]))
            self.url_icon.setToolTip("")
        elif url.scheme() == "https":
            self.url_icon.setIcon(make_icon("lock", t["muted"]))
            self.url_icon.setToolTip("Verbindung ist sicher")
        elif url.scheme() == "http":
            self.url_icon.setIcon(make_icon("alert", t["warn"]))
            self.url_icon.setToolTip("Verbindung ist nicht sicher")
        else:
            self.url_icon.setIcon(make_icon("search", t["muted"]))
            self.url_icon.setToolTip("")

    def toggle_theme(self):
        CFG["dark_mode"] = not CFG["dark_mode"]
        apply_theme()

    def toggle_adblock(self):
        CFG["adblock"] = not CFG["adblock"]
        for w in WINDOWS:
            w.refresh_icons()
        self.toast("Werbeblocker eingeschaltet" if CFG["adblock"] else "Werbeblocker ausgeschaltet")

    # ------------------------------------------------------------ Hinweise
    def toast(self, msg):
        self.toast_lbl.setText(msg)
        self.toast_lbl.adjustSize()
        self.toast_lbl.move(max(10, (self.stack.width() - self.toast_lbl.width()) // 2),
                            max(10, self.stack.height() - self.toast_lbl.height() - 28))
        self.toast_lbl.show()
        self.toast_lbl.raise_()
        self.toast_timer.start()

    def on_hover(self, link):
        if not link:
            self.hover.hide()
            return
        self.hover.setText(link if len(link) < 110 else link[:107] + "…")
        self.hover.adjustSize()
        self.hover.move(8, self.stack.height() - self.hover.height() - 8)
        self.hover.show()
        self.hover.raise_()

    def about(self):
        box = QMessageBox(self)
        box.setWindowTitle("Über NyroxNite")
        box.setIconPixmap(logo_icon().pixmap(64, 64))
        box.setText(f"<h2 style='margin:0'>NyroxNite</h2><p style='margin:2px 0 0 0'>by Tobias</p><p>Version {VERSION}</p>"
                    f"<p>Chromium-basierter Browser mit PyQt6.</p>"
                    f"<p style='color:gray'>Programmdatei: {html.escape(str(APP_FILE))}<br>"
                    f"Daten: {html.escape(str(DATA_DIR))}</p>")
        box.exec()

    # ------------------------------------------------------------ Tabs
    def view(self) -> WebView:
        return self.tabs.currentWidget()

    def add_tab(self, url=None, background=False, load=True):
        v = WebView(self)
        self.apply_web_settings(v)
        i = self.tabs.addTab(v, "Neuer Tab")
        self.tabs.setTabIcon(i, logo_icon())
        v.titleChanged.connect(lambda t, v=v: self.on_title(v, t))
        v.iconChanged.connect(lambda ic, v=v: self.on_icon(v, ic))
        v.urlChanged.connect(lambda u, v=v: self.on_url(v, u))
        v.loadStarted.connect(lambda v=v: self.on_load(v, True))
        v.loadProgress.connect(lambda p, v=v: self.on_progress(v, p))
        v.loadFinished.connect(lambda ok, v=v: self.on_load(v, False, ok))
        page = v.page()
        page.linkHovered.connect(self.on_hover)
        page.fullScreenRequested.connect(self.on_fullscreen_request)
        page.audioMutedChanged.connect(lambda _m, v=v: self.on_title(v, v.title()))
        page.recentlyAudibleChanged.connect(lambda _a, v=v: self.on_title(v, v.title()))
        page.windowCloseRequested.connect(lambda v=v: self.close_tab(self.tabs.indexOf(v)))
        page.renderProcessTerminated.connect(lambda st, code, v=v: self.on_render_crash(v, st, code))
        target = None
        if load:
            if url is None or (isinstance(url, QUrl) and url.isEmpty()):
                url = NEWTAB_URL
            target = url if isinstance(url, QUrl) else QUrl.fromUserInput(str(url))
            v.setUrl(target)
        if not background:
            self.tabs.setCurrentIndex(i)
            if target is not None and is_newtab(target):
                QTimer.singleShot(60, self.focus_urlbar)
        return v

    def close_tab(self, i):
        if i < 0 or i >= self.tabs.count():
            return
        v = self.tabs.widget(i)
        if not self.private and v.url().isValid() and not is_newtab(v.url()):
            self.closed_tabs.append(v.url())
        self.tabs.removeTab(i)
        v.deleteLater()
        if self.tabs.count() == 0:
            self.close()

    def reopen_tab(self):
        if self.closed_tabs:
            self.add_tab(self.closed_tabs.pop())

    def tab_menu(self, pos):
        bar = self.tabs.tabBar()
        i = bar.tabAt(pos)
        m = QMenu(self)
        m.addAction("Neuer Tab", lambda: self.add_tab())
        if i >= 0:
            v = self.tabs.widget(i)
            m.addAction("Neu laden", v.reload)
            m.addAction("Duplizieren", lambda: self.add_tab(QUrl(v.url())))
            muted = v.page().isAudioMuted()
            m.addAction("Ton einschalten" if muted else "Tab stummschalten",
                        lambda: v.page().setAudioMuted(not muted))
            m.addSeparator()
            m.addAction("Tab schließen", lambda: self.close_tab(self.tabs.indexOf(v)))
            m.addAction("Andere Tabs schließen", lambda: self.close_others(v))
            m.addAction("Tabs rechts schließen", lambda: self.close_right(v))
        m.addAction("Geschlossenen Tab wiederherstellen", self.reopen_tab)
        m.exec(bar.mapToGlobal(pos))

    def close_others(self, keep):
        for j in range(self.tabs.count() - 1, -1, -1):
            if self.tabs.widget(j) is not keep:
                self.close_tab(j)

    def close_right(self, v):
        i = self.tabs.indexOf(v)
        for j in range(self.tabs.count() - 1, i, -1):
            self.close_tab(j)

    # ------------------------------------------------------------ Ereignisse
    def on_title(self, v, title):
        i = self.tabs.indexOf(v)
        if i < 0:
            return
        page = v.page()
        prefix = "🔇 " if page.isAudioMuted() else ("🔊 " if page.recentlyAudible() else "")
        t = title or v.url().toString() or "Neuer Tab"
        if is_newtab(v.url()):
            t = "Neuer Tab"
        self.tabs.setTabText(i, prefix + t)
        self.tabs.setTabToolTip(i, t)
        if v is self.view():
            self.setWindowTitle(f"{t} – {APP_NAME}" + (" (Privat)" if self.private else ""))

    def on_icon(self, v, ic):
        i = self.tabs.indexOf(v)
        if i >= 0:
            self.tabs.setTabIcon(i, logo_icon() if (ic.isNull() or is_newtab(v.url())) else ic)

    def on_url(self, v, url):
        if v is self.view():
            self.update_urlbar(url)
        z = CFG["zoom"].get(url.host())
        v.setZoomFactor(z if z else 1.0)
        if v is self.view():
            self.update_zoom_label()

    def update_urlbar(self, url):
        if not self.urlbar.hasFocus():
            s = url.toString()
            self.urlbar.setText("" if (is_newtab(url) or s == "about:blank") else s)
            self.urlbar.setCursorPosition(0)
        self.update_url_icon(url)
        self.update_star()
        self.update_nav()

    def on_progress(self, v, p):
        if v is self.view():
            self.loadbar.setValue(p)

    def on_render_crash(self, v, status, code):
        if status == QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
            return
        url = QUrl(v.url())
        try:
            with CRASH_FILE.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] Seite abgestürzt ({status}, Code {code}): {url.toString()}\n")
        except Exception:
            pass
        if v is self.view():
            self.show_banner("Diese Seite ist abgestürzt.", "Neu laden", lambda: v.setUrl(url), "alert")
        else:
            QTimer.singleShot(0, lambda: v.setUrl(url))

    def on_load(self, v, started, ok=True):
        if not started and not self.private:
            schedule_session_save()
        if not started and ok and not self.private:
            u = v.url().toString()
            if u.startswith("http"):
                hist = CFG.data.setdefault("history", [])
                entry = {"url": u, "title": v.title(), "time": datetime.now().strftime("%d.%m.%Y %H:%M")}
                if hist and hist[-1]["url"] == u:
                    hist[-1] = entry
                else:
                    hist.append(entry)
                CFG.save()
                self.update_completer()
        if v is not self.view():
            return
        self.loading = started
        self.loadbar.setValue(5 if started else 0)
        self.reload_btn.setIcon(make_icon("stop" if started else "reload", theme()["text"]))
        self.reload_btn.setToolTip("Laden stoppen" if started else "Neu laden (F5)")
        self.update_nav()

    def on_tab_changed(self, _i):
        v = self.view()
        if not v:
            return
        self.loading = False
        self.loadbar.setValue(0)
        self.reload_btn.setIcon(make_icon("reload", theme()["text"]))
        self.update_urlbar(v.url())
        self.on_title(v, v.title())
        self.update_zoom_label()
        if self.find_bar.isVisible():
            self.find(False)

    def update_nav(self):
        v = self.view()
        if v:
            self.back_btn.setEnabled(v.history().canGoBack())
            self.fwd_btn.setEnabled(v.history().canGoForward())

    def update_completer(self):
        seen, items = set(), []
        for h in reversed(CFG["history"]):
            if h["url"] not in seen:
                seen.add(h["url"])
                items.append(h["url"])
            if len(items) > 500:
                break
        items += [b["url"] for b in CFG["bookmarks"] if b["url"] not in seen]
        self.completer_model.setStringList(items)

    # ------------------------------------------------------------ Navigation
    def focus_urlbar(self):
        self.urlbar.setFocus()
        self.urlbar.selectAll()

    def on_completion(self, text):
        self.urlbar.setText(text)
        self.navigate()

    def navigate(self):
        text = self.urlbar.text().strip()
        if not text:
            return
        if "://" in text or text.startswith(("about:", "view-source:", "file:")):
            url = QUrl(text)
        elif " " not in text and ("." in text or text.startswith("localhost")):
            url = QUrl.fromUserInput(text)
        else:
            url = QUrl(SEARCH_ENGINES[CFG["search_engine"]].format(quote_plus(text)))
        self.view().setUrl(url)
        self.view().setFocus()

    def go_home(self):
        self.view().setUrl(home_url())

    def reload_or_stop(self):
        if self.loading:
            self.view().stop()
        else:
            self.view().reload()

    def on_escape(self):
        if self.find_bar.isVisible():
            self.hide_find()
        elif self.isFullScreen():
            self.toggle_fullscreen()

    # ------------------------------------------------------------ Lesezeichen
    def is_bookmarked(self, url):
        return any(b["url"] == url for b in CFG["bookmarks"])

    def update_star(self):
        if not hasattr(self, "star_act") or not hasattr(self, "tabs"):
            return
        v = self.view()
        t = theme()
        if v and self.is_bookmarked(v.url().toString()):
            self.star_act.setIcon(make_icon("star", t["accent"], fill=t["accent"]))
        else:
            self.star_act.setIcon(make_icon("star", t["muted"]))
        self.star_act.setVisible(bool(v) and not is_newtab(v.url()))

    def toggle_bookmark(self):
        v = self.view()
        u = v.url().toString()
        if not u or is_newtab(v.url()):
            return
        if self.is_bookmarked(u):
            CFG["bookmarks"] = [b for b in CFG["bookmarks"] if b["url"] != u]
            self.toast("Lesezeichen entfernt")
        else:
            t, ok = QInputDialog.getText(self, "Lesezeichen hinzufügen", "Name:", text=v.title())
            if not ok:
                return
            CFG["bookmarks"] = CFG["bookmarks"] + [{"title": t or u, "url": u}]
            self.toast("Lesezeichen gespeichert")
        bookmarks_changed()

    # ------------------------------------------------------------ Suchen
    def show_find(self):
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self.update_esc()

    def hide_find(self):
        self.find_bar.hide()
        self.view().findText("")
        self.find_count.setText("")
        self.update_esc()

    def find(self, backward):
        flags = QWebEnginePage.FindFlag(0)
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        if self.find_case.isChecked():
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively
        text = self.find_input.text()
        if not text:
            self.view().findText("")
            self.find_count.setText("")
            return

        def done(res):
            n = res.numberOfMatches()
            self.find_count.setText(f"{res.activeMatch()} von {n}" if n else "Keine Treffer")
        self.view().findText(text, flags, done)

    # ------------------------------------------------------------ Zoom / Vollbild
    def zoom(self, delta):
        v = self.view()
        f = 1.0 if delta == 0 else max(0.25, min(5.0, round(v.zoomFactor() + delta, 2)))
        v.setZoomFactor(f)
        self.update_zoom_label()
        if not self.private:
            host = v.url().host()
            if host:
                if f == 1.0:
                    CFG.data["zoom"].pop(host, None)
                else:
                    CFG.data["zoom"][host] = f
                CFG.save()

    def update_zoom_label(self):
        v = self.view()
        if not v:
            return
        z = round(v.zoomFactor() * 100)
        self.zoom_btn.setText(f"{z} %")
        self.zoom_btn.setVisible(z != 100)

    def set_chrome_visible(self, visible):
        for w in (self.tabrow, self.navrow, self.loadbar):
            w.setVisible(visible)
        self.bm_bar.setVisible(visible and bool(CFG["show_bookmarks"]))
        if not visible:
            self.banner.hide()
            self.find_bar.hide()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.set_chrome_visible(True)
        else:
            self.showFullScreen()
        self.update_esc()

    def on_fullscreen_request(self, req):  # z. B. Videos
        req.accept()
        if req.toggleOn():
            self.set_chrome_visible(False)
            self.showFullScreen()
        elif self.isFullScreen():
            self.showNormal()
            self.set_chrome_visible(True)
        self.update_esc()

    # ------------------------------------------------------------ Speichern / Drucken / Werkzeuge
    def _safe_name(self, ext):
        name = re.sub(r'[\\/:*?"<>|]+', "_", self.view().title() or "seite").strip()[:80] or "seite"
        return os.path.join(CFG["download_dir"], name + ext)

    def save_page(self):
        p, _ = QFileDialog.getSaveFileName(self, "Seite speichern", self._safe_name(".mhtml"),
                                           "Webarchiv (*.mhtml);;Nur HTML (*.html)")
        if p:
            fmt = (QWebEngineDownloadRequest.SavePageFormat.SingleHtmlSaveFormat if p.endswith(".html")
                   else QWebEngineDownloadRequest.SavePageFormat.MimeHtmlSaveFormat)
            self.view().page().save(p, fmt)
            self.toast("Seite wird gespeichert …")

    def save_pdf(self):
        p, _ = QFileDialog.getSaveFileName(self, "Als PDF speichern", self._safe_name(".pdf"), "PDF (*.pdf)")
        if p:
            self.view().page().printToPdf(p)
            self.toast("PDF gespeichert")

    def print_page(self):
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            self._printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if QPrintDialog(self._printer, self).exec() == QDialog.DialogCode.Accepted:
                self.view().print(self._printer)
        except Exception:
            self.save_pdf()

    def view_source(self):
        self.add_tab(QUrl("view-source:" + self.view().url().toString()))

    def toggle_devtools(self):
        if self.devtools and self.devtools.isVisible():
            self.devtools.close()
            return
        self.devtools = QWebEngineView()
        self.devtools.setWindowTitle("Entwicklertools – NyroxNite")
        self.devtools.setWindowIcon(logo_icon())
        self.devtools.resize(1000, 650)
        self.view().page().setDevToolsPage(self.devtools.page())
        self.devtools.show()

    # ------------------------------------------------------------ Einstellungen
    def apply_web_settings(self, view=None):
        views = [view] if view else [self.tabs.widget(i) for i in range(self.tabs.count())]
        A = QWebEngineSettings.WebAttribute
        for v in views:
            s = v.settings()
            s.setAttribute(A.JavascriptEnabled, bool(CFG["javascript"]))
            s.setAttribute(A.PluginsEnabled, True)
            s.setAttribute(A.PdfViewerEnabled, True)
            s.setAttribute(A.FullScreenSupportEnabled, True)
            s.setAttribute(A.ScrollAnimatorEnabled, True)
            s.setAttribute(A.JavascriptCanOpenWindows, not CFG["block_popups"])
            s.setAttribute(A.ScreenCaptureEnabled, True)
            s.setAttribute(A.PlaybackRequiresUserGesture, False)
            s.setAttribute(A.LocalContentCanAccessRemoteUrls, True)
            if hasattr(A, "ForceDarkMode"):
                s.setAttribute(A.ForceDarkMode, bool(CFG["force_dark_web"]))

    def showEvent(self, e):
        super().showEvent(e)
        set_dark_titlebar(self, theme()["dark"])

    def closeEvent(self, e):
        save_all_sessions()
        if self.devtools:
            self.devtools.close()
        if self in WINDOWS:
            WINDOWS.remove(self)
        super().closeEvent(e)


def show_downloads():
    DOWNLOADS.show()
    DOWNLOADS.raise_()
    DOWNLOADS.activateWindow()


# ====================================================================== Start
def excepthook(et, ev, tb):
    msg = "".join(traceback.format_exception(et, ev, tb))
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%d.%m.%Y %H:%M:%S}] Version {VERSION}\n{msg}")
    except Exception:
        pass
    sys.__stderr__ and sys.__stderr__.write(msg)
    if WINDOWS:
        WINDOWS[0].toast("Ein Fehler ist aufgetreten – Details in fehler.log")


def main():
    global DOWNLOADS, UPDATER
    sys.excepthook = excepthook

    # --- Absturzschutz: Native Abstürze protokollieren, nach Absturz abgesicherten Modus nutzen
    try:
        import faulthandler
        crash_log = CRASH_FILE.open("a", encoding="utf-8")
        crash_log.write(f"\n--- Start {datetime.now():%d.%m.%Y %H:%M:%S} · Version {VERSION} · "
                        f"Hardwarebeschleunigung {'an' if CFG['hardware_accel'] else 'aus'} ---\n")
        crash_log.flush()
        faulthandler.enable(crash_log)
    except Exception:
        pass
    crashed = bool(CFG["running"])
    switched_safe = False
    if crashed:
        CFG.data["crash_count"] = int(CFG["crash_count"] or 0) + 1
        if CFG["hardware_accel"]:
            CFG.data["hardware_accel"] = False
            switched_safe = True
    CFG.data["running"] = True
    CFG.save()
    if not CFG["hardware_accel"]:
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --disable-gpu --disable-gpu-compositing").strip()
        if QApplication.instance() is None:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_FULL)
    app.setWindowIcon(logo_icon())
    apply_theme()
    DOWNLOADS = DownloadsDialog()
    UPDATER = Updater()

    args = [a for a in sys.argv[1:] if not a.startswith("-") and not a.lower().endswith((".py", ".exe"))]
    restore = CFG["restore_once"] or CFG["restore_session"] or crashed
    CFG["restore_once"] = False
    if args:
        win = new_window(args)
    elif restore and CFG["session"]:
        win = new_window(CFG["session"])
    else:
        win = new_window()

    if switched_safe:
        win.show_banner("NyroxNite wurde unerwartet beendet. Der abgesicherte Grafikmodus ist jetzt aktiv, "
                        "damit das nicht wieder passiert. Deine Tabs wurden wiederhergestellt.",
                        "Einstellungen", lambda: SettingsDialog(win).exec(), "alert")
    elif crashed:
        win.show_banner("NyroxNite wurde unerwartet beendet. Deine Tabs wurden wiederhergestellt.",
                        "OK", None, "alert")

    last = CFG["last_version"]
    if last != VERSION:
        if last and not crashed:
            win.show_banner(f"{APP_FULL} – Version {VERSION} ist installiert.", "Neuigkeiten ansehen",
                            lambda: show_changelog(win), "sparkle")
        CFG["last_version"] = VERSION

    app.aboutToQuit.connect(on_quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
