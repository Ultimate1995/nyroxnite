@echo off
chcp 65001 >nul
title NyroxNite Browser by Tobias - EXE erstellen
cd /d "%~dp0"
echo ============================================
echo   NyroxNite Browser by Tobias wird gebaut
echo ============================================
echo.

for %%E in (NyroxNite.exe NovaBrowser.exe) do (
    tasklist /fi "imagename eq %%E" 2>nul | find /i "%%E" >nul
    if not errorlevel 1 (
        echo Browser laeuft gerade und wird fuer den Neubau geschlossen ...
        taskkill /im %%E /f >nul 2>nul
        timeout /t 2 /nobreak >nul
    )
)

set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
    echo [FEHLER] Python wurde nicht gefunden.
    echo Bitte installiere Python von https://www.python.org/downloads/
    echo und setze beim Installieren das Haekchen "Add Python to PATH".
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Benoetigte Pakete werden installiert ...
%PY% -m pip install --upgrade pip
%PY% -m pip install --upgrade PyQt6 PyQt6-WebEngine pyinstaller
if errorlevel 1 (
    echo [FEHLER] Installation der Pakete fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo [2/3] EXE wird gebaut (das dauert 1-3 Minuten) ...
%PY% -m PyInstaller --noconfirm --clean --windowed --name NyroxNite --add-data "browser.py;." launcher.py
if errorlevel 1 (
    echo [FEHLER] Der Build ist fehlgeschlagen. Bitte die Meldungen oben pruefen.
    pause
    exit /b 1
)

echo.
echo [3/3] Aufraeumen und Verknuepfung erstellen ...
if exist "dist\NovaBrowser" rmdir /s /q "dist\NovaBrowser"
if exist "build\NovaBrowser" rmdir /s /q "build\NovaBrowser"
if exist "NovaBrowser.spec" del /q "NovaBrowser.spec"
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item -ErrorAction SilentlyContinue ($d+'\NovaBrowser.lnk'),($d+'\NyroxNite by Tobias.lnk'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\NyroxNite Browser by Tobias.lnk');$s.TargetPath='%~dp0dist\NyroxNite\NyroxNite.exe';$s.WorkingDirectory='%~dp0dist\NyroxNite';$s.Save()"

echo.
echo Paket zum Weitergeben wird erstellt (ZIP) ...
if exist "NyroxNite_zum_Weitergeben.zip" del /q "NyroxNite_zum_Weitergeben.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%~dp0dist\NyroxNite' -DestinationPath '%~dp0NyroxNite_zum_Weitergeben.zip' -Force"

echo.
echo ============================================
echo   Fertig!
echo   Programm: %~dp0dist\NyroxNite\NyroxNite.exe
echo   Verknuepfung "NyroxNite Browser by Tobias" liegt auf dem Desktop.
echo   Zum Weitergeben: %~dp0NyroxNite_zum_Weitergeben.zip
echo.
echo   Updates an browser.py werden ab jetzt automatisch
echo   uebernommen - die EXE muss nicht neu gebaut werden.
echo ============================================
start "" "%~dp0dist\NyroxNite\NyroxNite.exe"
pause
