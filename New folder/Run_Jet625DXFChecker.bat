@echo off
title Donatoni Jet 625 DXF Checker
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
        echo.
        echo Install Python from python.org and make sure "Add Python to PATH" is checked.
        pause
        exit /b 1
    )
)

echo Installing/updating required package...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install ezdxf

if %errorlevel% neq 0 (
    echo.
    echo Could not install ezdxf.
    pause
    exit /b 1
)

echo.
echo Starting Jet 625 DXF Checker...
%PY_CMD% "%~dp0jet_625_dxf_validator.py"
