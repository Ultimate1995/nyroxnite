@echo off
chcp 65001 >nul
setlocal
title NyroxNite Browser by Tobias - bauen
cd /d "%~dp0"
echo ======================================================
echo   NyroxNite Browser by Tobias wird gebaut  -  Version 3
echo ======================================================
echo.

tasklist /fi "imagename eq NyroxNite.exe" 2>nul | find /i "NyroxNite.exe" >nul
if not errorlevel 1 (
    echo NyroxNite laeuft gerade und wird fuer den Neubau geschlossen ...
    taskkill /im NyroxNite.exe /f >nul 2>nul
    timeout /t 2 /nobreak >nul
)

where npm >nul 2>nul
if errorlevel 1 goto :nonode
goto :hasnode

:nonode
echo [!] Node.js ist nicht installiert - es wird jetzt installiert ...
where winget >nul 2>nul
if errorlevel 1 (
    start https://nodejs.org/
    echo Bitte Node.js LTS von nodejs.org installieren.
) else (
    winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
)
echo.
echo Danach dieses Fenster schliessen und NyroxNite_bauen.bat erneut starten.
pause
exit /b 1

:hasnode
echo [1/5] Browser-Engine wird heruntergeladen - beim ersten Mal ca. 150 MB ...
call npm install --no-audit --no-fund
if errorlevel 1 (
    echo [FEHLER] Download der Engine fehlgeschlagen. Bitte Internetverbindung pruefen.
    pause
    exit /b 1
)
if not exist "node_modules\electron\dist\electron.exe" (
    echo [FEHLER] Die Engine wurde nicht vollstaendig heruntergeladen.
    echo Loesche den Ordner node_modules und starte das Skript erneut.
    pause
    exit /b 1
)

echo.
echo [2/5] Programmordner wird erstellt ...
set "OUT=%~dp0dist\NyroxNite"
if exist "%OUT%" rmdir /s /q "%OUT%"
robocopy "node_modules\electron\dist" "%OUT%" /E /NFL /NDL /NJH /NJS /NP >nul
ren "%OUT%\electron.exe" NyroxNite.exe
if exist "%OUT%\resources\default_app.asar" del /q "%OUT%\resources\default_app.asar"
mkdir "%OUT%\resources\app" >nul 2>nul
copy /y package.json "%OUT%\resources\app\" >nul
copy /y boot.js "%OUT%\resources\app\" >nul
robocopy "core" "%OUT%\resources\app\core" /E /NFL /NDL /NJH /NJS /NP >nul
robocopy "assets" "%OUT%\resources\app\assets" /E /NFL /NDL /NJH /NJS /NP >nul

echo [3/5] Programmsymbol wird gesetzt ...
set "RCEDIT=node_modules\rcedit\bin\rcedit-x64.exe"
if not exist "%RCEDIT%" set "RCEDIT=node_modules\rcedit\bin\rcedit.exe"
if exist "%RCEDIT%" (
    "%RCEDIT%" "%OUT%\NyroxNite.exe" --set-icon "assets\icon.ico" --set-version-string "ProductName" "NyroxNite Browser" --set-version-string "FileDescription" "NyroxNite Browser by Tobias" --set-version-string "CompanyName" "Tobias"
) else (
    echo     rcedit nicht gefunden - Symbol wird uebersprungen.
)

echo.
echo [4/5] Freischaltung fuer Netflix und Co. - Widevine VMP-Signatur ...
set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY goto :nopy
%PY% -m pip install --upgrade --quiet castlabs-evs
%PY% -m castlabs_evs.vmp sign-pkg "%OUT%"
if not errorlevel 1 goto :signed
echo.
echo ------------------------------------------------------------------
echo  Fuer Netflix braucht NyroxNite einmalig ein KOSTENLOSES Konto bei
echo  castLabs - dem Anbieter des Netflix-Kopierschutzes.
echo  Bitte gib gleich die abgefragten Daten ein: E-Mail, Name, Passwort.
echo ------------------------------------------------------------------
%PY% -m castlabs_evs.account signup
%PY% -m castlabs_evs.vmp sign-pkg "%OUT%"
if not errorlevel 1 goto :signed
echo [!] Signatur fehlgeschlagen - Netflix funktioniert evtl. nicht. Twitch und Co. laufen trotzdem.
goto :afterSign
:nopy
echo [!] Python nicht gefunden - Signatur uebersprungen. Netflix funktioniert evtl. nicht.
goto :afterSign
:signed
echo     Signatur erfolgreich - Netflix und Co. sind freigeschaltet.
:afterSign

echo.
echo [5/5] Verknuepfung und ZIP zum Weitergeben ...
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item -ErrorAction SilentlyContinue ($d+'\NovaBrowser.lnk'),($d+'\NyroxNite by Tobias.lnk'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\NyroxNite Browser by Tobias.lnk'); $s.TargetPath='%OUT%\NyroxNite.exe'; $s.WorkingDirectory='%OUT%'; $s.IconLocation='%OUT%\NyroxNite.exe,0'; $s.Save()"
if exist "NyroxNite_zum_Weitergeben.zip" del /q "NyroxNite_zum_Weitergeben.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%OUT%' -DestinationPath '%~dp0NyroxNite_zum_Weitergeben.zip' -Force"

echo.
echo ======================================================
echo   Fertig!
echo   Programm:        %OUT%\NyroxNite.exe
echo   Verknuepfung:    "NyroxNite Browser by Tobias" auf dem Desktop
echo   Zum Weitergeben: %~dp0NyroxNite_zum_Weitergeben.zip
echo.
echo   Updates kommen ab jetzt automatisch auf jeden PC.
echo ======================================================
start "" "%OUT%\NyroxNite.exe"
pause
