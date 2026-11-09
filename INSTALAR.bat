@echo off
cd /d "%~dp0"
rem Instalador grafico de NOVA AI. Lo normal es abrir directamente "NOVA AI Setup.exe".
if exist "%~dp0NOVA AI Setup.exe" (
  start "" "%~dp0NOVA AI Setup.exe"
  exit /b 0
)
rem Sin el .exe: el mismo instalador grafico con PowerShell (pide permiso de administrador).
powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0instalador\instalador.ps1" -Origen "%~dp0."
if %errorlevel% geq 2 (
  echo.
  echo  No se pudo abrir el instalador grafico. Usando el instalador de consola...
  echo  ^(instala NOVA en esta misma carpeta, sin accesos directos ni desinstalador^)
  if exist "%TEMP%\NOVA_AI_Setup_error.log" type "%TEMP%\NOVA_AI_Setup_error.log"
  echo.
  call "%~dp0INSTALAR_CONSOLA.bat"
)
