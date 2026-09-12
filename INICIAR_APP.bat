@echo off
cd /d "%~dp0"
title FICHA DE CARACTERIZACION PWA - LEMON FABRICA
color 0A

set PYTHON_CMD=
python --version > nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py --version > nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor instala Python o agregalo a las variables de entorno.
    pause
    exit /b 1
)

echo [OK] Iniciando Digitalizador de Fichas PWA con %PYTHON_CMD%...
"%PYTHON_CMD%" backend/main.py

pause
