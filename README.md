# NyroxNite by Tobias

Ein moderner Desktop-Browser auf Basis von Chromium (PyQt6 + QtWebEngine).

## Installation (Windows)

1. Python installieren (https://www.python.org/downloads/, Häkchen bei „Add Python to PATH“).
2. `EXE_erstellen.bat` doppelklicken – baut `dist\NyroxNite\NyroxNite.exe` und eine ZIP zum Weitergeben.

## Updates

Jeder NyroxNite prüft beim Start und alle 30 Minuten `browser.py` in diesem Repository.
Ist dort eine höhere `VERSION` eingetragen, wird das Update heruntergeladen und nach einem
Neustart installiert. Die EXE muss dafür nicht neu gebaut werden.

## Dateien

- `browser.py` – der eigentliche Browser (wird online aktualisiert)
- `launcher.py` – Starter, der zur EXE gebaut wird und immer die neueste `browser.py` lädt
- `EXE_erstellen.bat` – baut die EXE unter Windows
