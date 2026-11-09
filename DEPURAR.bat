@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Modo depuracion: los mensajes y errores salen en esta ventana (y en nova.log, dentro de tu carpeta de datos)
.venv\Scripts\python.exe nova.py
pause
