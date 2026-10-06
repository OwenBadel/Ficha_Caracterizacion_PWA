@echo off
cd /d "%~dp0"
title FICHA DE CARACTERIZACION PWA - OWEN BADEL HOOKER
color 0A

echo =======================================================
echo   DIGITALIZADOR DE FICHAS PWA - OWEN BADEL HOOKER
echo   Arquitectura Soberana: Ollama Qwen3-VL con GPU NVIDIA
echo =======================================================
echo.

:: Verificar si Ollama esta corriendo; si no, iniciarlo en segundo plano
curl -s http://localhost:11434/ > nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Iniciando motor local de Ollama en segundo plano...
    start /b "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve > nul 2>&1
    timeout /t 3 /nobreak > nul
)

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
