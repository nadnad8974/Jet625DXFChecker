@echo off
title Build Jet625DXFChecker EXE
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PY_CMD=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PY_CMD=python
    ) else (
        echo Python is not installed.
        pause
        exit /b 1
    )
)

%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install ezdxf pyinstaller

if %errorlevel% neq 0 (
    echo Failed to install build requirements.
    pause
    exit /b 1
)

%PY_CMD% -m PyInstaller --noconfirm --onefile --windowed --name Jet625DXFChecker jet_625_dxf_validator.py

echo.
echo If build worked, your EXE is here:
echo dist\Jet625DXFChecker.exe
pause
