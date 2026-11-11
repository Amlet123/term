@echo off
rem Все параметры со скриптом startup/all_commands.emu
rem Запуск: scripts\run_all_commands.bat (из любой папки)
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
if not defined PYTHON set PYTHON=python
cd /d "%~dp0.."
set EMU_DEMO_DIR=C:\demo

echo.
echo === 1. Без параметров (команды через stdin) ===
echo exit| %PYTHON% src/terminalus.py

echo.
echo === 2. Только --vfs ===
echo exit| %PYTHON% src/terminalus.py --vfs data/disk.xml

echo.
echo === 3. Только --script ===
%PYTHON% src/terminalus.py --script startup/all_commands.emu

echo.
echo === 4. Оба параметра ===
%PYTHON% src/terminalus.py --vfs data/disk.xml --script startup/all_commands.emu

echo.
echo === 5. Справка --help ===
%PYTHON% src/terminalus.py --help

endlocal
