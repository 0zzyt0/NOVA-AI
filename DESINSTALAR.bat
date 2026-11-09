@echo off
rem Desinstala NOVA AI (tambien desde Configuracion > Aplicaciones o el menu Inicio).
if exist "%ProgramFiles%\NOVA AI\Desinstalar NOVA AI.exe" (
  start "" "%ProgramFiles%\NOVA AI\Desinstalar NOVA AI.exe"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0instalador\desinstalar.ps1"
