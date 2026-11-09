@echo off
chcp 65001 >nul
title Instalador de NOVA (modo consola)
cd /d "%~dp0"
echo.
echo  ===  NOVA - Asistente de vuelo para Star Citizen  ===
echo.
echo  Antes de instalar, lee las Normas de uso y la Politica de privacidad
echo  (NORMAS_Y_PRIVACIDAD.md, se abre en el Bloc de notas). En resumen: tus datos se quedan
echo  en tu PC, no se hacen grabaciones y las consultas a internet son las mismas que harias
echo  tu en Google o en una IA.
if exist "%~dp0NORMAS_Y_PRIVACIDAD.md" start "" notepad "%~dp0NORMAS_Y_PRIVACIDAD.md"
echo.
choice /c SN /n /m " Aceptas las Normas de uso y la Politica de privacidad? [S/N] "
if errorlevel 2 (
  echo  Instalacion cancelada: hay que aceptar las normas para instalar NOVA.
  pause
  exit /b 1
)
echo.
rem Solo valen Python 3.11, 3.12 o 3.13 de 64 bits: las versiones mas nuevas (3.14, 3.15...)
rem todavia no tienen versiones precompiladas de pygame, Whisper, etc.
set "CHECK=import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32 else 1)"
set "OWNPY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "PY="
py -3.12 -c "%CHECK%" >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3.11 -c "%CHECK%" >nul 2>&1 && set "PY=py -3.11"
if not defined PY py -3.13 -c "%CHECK%" >nul 2>&1 && set "PY=py -3.13"
if not defined PY if exist "%OWNPY%" "%OWNPY%" -c "%CHECK%" >nul 2>&1 && set PY="%OWNPY%"
if not defined PY python -c "%CHECK%" >nul 2>&1 && set "PY=python"
if defined PY goto :havepy

echo  No hay un Python compatible (3.11 a 3.13). Si tienes uno mas nuevo, no pasa nada:
echo  se instala Python 3.12 aparte, solo para Nova, sin tocar el que ya tienes.
echo.
echo  Descargando Python 3.12 (unos 25 MB)...
curl.exe -L --fail --progress-bar -o "%TEMP%\python-3.12.10-amd64.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
if errorlevel 1 goto :nopython
echo  Instalando Python 3.12 para tu usuario (1-2 minutos)...
start "" /wait "%TEMP%\python-3.12.10-amd64.exe" /quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_doc=0 Include_launcher=1 InstallLauncherAllUsers=0 Shortcuts=0
if not exist "%OWNPY%" goto :nopython
set PY="%OWNPY%"

:havepy
echo  Usando: %PY%
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "%CHECK%" >nul 2>&1 || (
    echo  El entorno anterior se creo con un Python no compatible: se vuelve a crear...
    rmdir /s /q .venv
  )
)
if not exist .venv\Scripts\python.exe (
  echo  Creando entorno de Python...
  %PY% -m venv .venv || (echo Error creando el entorno & pause & exit /b 1)
)
set "VPY=.venv\Scripts\python.exe"
set "PIPI=%VPY% -m pip install --prefer-binary --only-binary=numpy,pillow,pygame,ctranslate2,onnxruntime,av,tokenizers,rapidfuzz,miniaudio,sounddevice"
%VPY% -m pip install --upgrade pip
echo.
echo  Instalando lo imprescindible...
%PIPI% -r requirements.txt || (echo. & echo  Error instalando dependencias. Revisa tu conexion e intentalo de nuevo. & pause & exit /b 1)
echo.
echo  Instalando reconocimiento de voz local (Whisper)...
%PIPI% "faster-whisper>=1.1" || echo  [aviso] Whisper local no instalado: usa Groq para reconocer la voz.
echo  Instalando busqueda en internet...
%PIPI% "ddgs>=9.0" || echo  [aviso] Busqueda web no instalada.
echo  Instalando soporte de joystick/HOTAS...
%PIPI% "pygame>=2.5" || echo  [aviso] Joystick no disponible: usa una tecla o el raton para hablar.
echo  Instalando voces de respaldo...
%PIPI% "pyttsx3>=2.90" || echo  [aviso] Voz de Windows no instalada.
%PIPI% piper-tts || echo  [aviso] Piper no instalado: Edge sigue funcionando.
where nvidia-smi >nul 2>&1 && (
  echo.
  echo  Tarjeta NVIDIA detectada: instalando aceleracion CUDA para Whisper local...
  %PIPI% nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" || echo  [aviso] CUDA no instalado: Whisper local usara la CPU.
)
echo.
echo  ===  Listo. Ejecuta INICIAR.bat  ===
pause
exit /b 0

:nopython
echo.
echo  No se pudo descargar o instalar Python 3.12 automaticamente.
echo  Descargalo a mano (Windows installer 64-bit) e instalalo; luego vuelve a ejecutar este instalador:
echo  https://www.python.org/downloads/release/python-31210/
start https://www.python.org/downloads/release/python-31210/
pause
exit /b 1
