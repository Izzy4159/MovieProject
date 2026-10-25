@echo off
rem ── Movie Poster Explorer launcher ──────────────────────────────────────────
rem Starts the server from .venv and opens the browser once it answers.
rem If the server is already running, just opens the browser.
rem "Launch MovieProject (silent).vbs" runs this with no window (MP_SILENT=1)
rem and the server log goes to server.log instead.
setlocal
cd /d "%~dp0"

if not defined PORT set "PORT=5000"
set "URL=http://127.0.0.1:%PORT%/"

rem Re-entry point: background poller started below
if "%~1"==":open-when-up" goto open_when_up

rem Already running (any version of the app)? Just open it.
curl -s -f -o nul --max-time 2 "%URL%manifest.webmanifest" && (
    echo Movie Poster Explorer is already running - opening %URL%
    start "" "%URL%"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  .venv not found in "%CD%".
    echo  Create it once with:
    echo.
    echo      python -m venv .venv
    echo      .venv\Scripts\python -m pip install -r requirements.txt
    echo.
    if not "%MP_SILENT%"=="1" pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

rem Poll in the background so the server's log stays in this window
start "" /b cmd /c ""%~f0" :open-when-up"

if "%MP_SILENT%"=="1" (
    python -u main.py --no-browser --port %PORT% > server.log 2>&1
) else (
    title Movie Poster Explorer
    python main.py --no-browser --port %PORT%
)
exit /b %errorlevel%

:open_when_up
rem Up to 60 s: poll /health once a second, then open the browser
for /l %%i in (1,1,60) do (
    curl -s -f -o nul --max-time 2 "%URL%health" && goto open_browser
    ping -n 2 127.0.0.1 > nul
)
echo Server did not answer on %URL% within 60 seconds.
exit /b 1

:open_browser
start "" "%URL%"
exit /b 0
