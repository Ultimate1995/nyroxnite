"""
NyroxNite-Starter (wird zur NyroxNite.exe gebaut).

Die EXE enthält nur Python + Qt. Den eigentlichen Browser (browser.py) lädt sie
bei jedem Start aus dem Programmordner. Dadurch wirken Updates an browser.py
sofort – ohne die EXE neu zu bauen.
"""
import importlib.util
import sys
import traceback
from pathlib import Path

# --- Diese Importe sorgen dafür, dass PyInstaller alles Nötige in die EXE packt ---
import base64, collections, ctypes, faulthandler, dataclasses, datetime, functools, hashlib, html, itertools  # noqa: E401,F401
import json, math, os, random, re, shutil, string, subprocess, tempfile, threading, time       # noqa: E401,F401
import typing, urllib.parse, urllib.request, uuid, zipfile                                       # noqa: E401,F401
from PyQt6 import QtCore, QtGui, QtWidgets, QtSvg, QtNetwork, QtPrintSupport                     # noqa: F401
from PyQt6 import QtWebEngineCore, QtWebEngineWidgets                                            # noqa: F401
try:
    from PyQt6 import QtWebChannel  # noqa: F401
except ImportError:
    pass


def read_version(p):
    try:
        m = re.search(r'^VERSION\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8", errors="ignore"), re.M)
        return tuple(int(n) for n in re.findall(r"\d+", m.group(1))[:4]) if m else (0,)
    except Exception:
        return (0,)


def candidates():
    """Alle verfügbaren browser.py – die mit der höchsten Version zuerst.

    1. neben der EXE / bis zu 3 Ordner darüber (Entwickler-PC, z. B. D:\\NovaBrowser)
    2. online heruntergeladenes Update (%APPDATA%\\NyroxNite\\app)
    3. Notfall-Kopie, die in der EXE steckt
    """
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    found = []
    for d in [base, *list(base.parents)[:3]]:
        p = d / "browser.py"
        if p.exists():
            found.append(p)
            os.environ["NYROX_LOCAL_SOURCE"] = str(p)
            break
    appdata = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
    for name in ("NyroxNite", "NovaBrowser"):
        p = appdata / name / "app" / "browser.py"
        if p.exists():
            found.append(p)
    bundled = Path(getattr(sys, "_MEIPASS", base)) / "browser.py"
    if bundled.exists():
        found.append(bundled)
    unique = []
    for p in found:
        if p.resolve() not in [u.resolve() for u in unique]:
            unique.append(p)
    return sorted(unique, key=read_version, reverse=True)   # stabil: bei Gleichstand lokale Datei zuerst


def load(path):
    spec = importlib.util.spec_from_file_location("browser", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["browser"] = mod
    spec.loader.exec_module(mod)
    return mod


def show_error(text):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "NyroxNite – Fehler", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def main():
    errors = []
    for path in candidates():
        try:
            mod = load(path)
        except Exception:
            errors.append(f"{path}:\n{traceback.format_exc()}")
            continue
        sys.exit(mod.main())
    show_error("NyroxNite konnte nicht gestartet werden.\n\n" + ("\n\n".join(errors) or "browser.py wurde nicht gefunden."))


if __name__ == "__main__":
    main()
