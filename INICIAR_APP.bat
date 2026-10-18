@echo off
cd /d "%~dp0"
title FICHA DE CARACTERIZACION PWA - OWEN BADEL HOOKER
color 0A

echo =======================================================
echo   DIGITALIZADOR DE FICHAS PWA - OWEN BADEL HOOKER
echo   Vision: Google Gemini ^| Reconciliacion: Jaro-Winkler
echo =======================================================
echo.

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

echo [OK] Verificando IP local y conectividad movil...
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "0.0.0.0.*0.0.0.0"') do (
    set LOCAL_IP=%%a
)

echo.
echo =======================================================
echo   ACCESO DESDE CELULARES EN LA RED WI-FI:
echo   URL Local:   http://%LOCAL_IP%:8000
echo.
echo   * NOTA PWA OFFLINE EN CELULARES (Chrome Android):
echo     Para habilitar Service Worker e instalacion PWA en IP:
echo     Visita: chrome://flags/#unsafely-treat-insecure-origin-as-secure
echo     Escribe: http://%LOCAL_IP%:8000  (y activa 'Enabled')
echo.
echo   * TUNNEL HTTPS (OPCIONAL PARA DATOS MOVILES / 4G):
echo     Si descargas cloudflared.exe en esta carpeta, ejecuta:
echo     cloudflared tunnel --url http://localhost:8000
echo =======================================================
echo.

where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] cloudflared detectado. Iniciando tunel HTTPS seguro en segundo plano...
    start "CLOUDFLARED TUNNEL (HTTPS PWA)" cloudflared tunnel --url http://localhost:8000
)

echo [OK] Iniciando Digitalizador de Fichas PWA con %PYTHON_CMD%...
"%PYTHON_CMD%" backend/main.py

pause
