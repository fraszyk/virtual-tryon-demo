@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY (
    for %%C in (python3.exe python.exe) do (
        if not defined PY (
            where %%C >nul 2>&1 && (
                %%C -c "import sys" >nul 2>&1 && set "PY=%%C"
            )
        )
    )
)

if not defined PY (
    echo.
    echo === Python was not found on PATH. ===
    echo Install Python 3.10+ from https://www.python.org/downloads/windows/
    echo During install, tick "Add python.exe to PATH".
    echo.
    echo If you see a Microsoft Store popup when typing "python", open:
    echo    Settings ^> Apps ^> Advanced app settings ^> App execution aliases
    echo and turn OFF the "python.exe" and "python3.exe" aliases.
    echo.
    pause
    exit /b 1
)

echo Using Python: %PY%

if not exist .venv (
    echo Creating virtual environment...
    %PY% -m venv .venv || goto :err
)

call .venv\Scripts\activate.bat || goto :err

echo Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -q -r requirements.txt || goto :err

if not exist .env (
    echo.
    echo === No .env found. Copying .env.example to .env. ===
    echo === Edit .env and set OPENAI_API_KEY before generating images. ===
    echo.
    copy .env.example .env >nul
)

echo.
echo Starting server on http://localhost:5000 ...
python src\app.py
goto :eof

:err
echo.
echo Setup failed. See error above.
pause
exit /b 1
