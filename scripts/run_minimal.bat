@echo off
rem Все параметры со скриптом startup/minimal.emu
rem Запуск: scripts\run_minimal.bat (из любой папки)
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
if not defined PYTHON set PYTHON=python
cd /d "%~dp0.."
set "EMU_OUT_DIR=%TEMP%\terminalus_out"
if exist "%EMU_OUT_DIR%" rmdir /s /q "%EMU_OUT_DIR%"
mkdir "%EMU_OUT_DIR%"
set "EMU_DEMO_DIR=C:\demo"

echo.
echo === 1. Без параметров (команды через stdin) ===
echo exit| %PYTHON% src/terminalus.py

echo.
echo === 2. Только --vfs ===
echo exit| %PYTHON% src/terminalus.py --vfs vfs_samples/minimal.xml

echo.
echo === 3. Только --script ===
%PYTHON% src/terminalus.py --script startup/minimal.emu

echo.
echo === 4. Оба параметра ===
%PYTHON% src/terminalus.py --vfs vfs_samples/minimal.xml --script startup/minimal.emu

echo.
echo === 5. Справка --help ===
%PYTHON% src/terminalus.py --help

rmdir /s /q "%EMU_OUT_DIR%"
endlocal
