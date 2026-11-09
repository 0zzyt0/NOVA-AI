@echo off
cd /d "%~dp0"
rem Abre NOVA AI. Lo normal es usar el acceso directo "NOVA AI" del escritorio.
if exist "%ProgramFiles%\NOVA AI\NOVA AI.exe" if not exist .venv\Scripts\pythonw.exe (
  start "" "%ProgramFiles%\NOVA AI\NOVA AI.exe"
  exit /b 0
)
if exist .venv\Scripts\pythonw.exe (
  start "" .venv\Scripts\pythonw.exe nova.py
  exit /b 0
)
if exist "%ProgramFiles%\NOVA AI\.venv\Scripts\pythonw.exe" (
  start "" "%ProgramFiles%\NOVA AI\.venv\Scripts\pythonw.exe" "%ProgramFiles%\NOVA AI\nova.py"
  exit /b 0
)
echo Primero instala NOVA AI con "NOVA AI Setup.exe" (o INSTALAR.bat).
pause
exit /b 1
