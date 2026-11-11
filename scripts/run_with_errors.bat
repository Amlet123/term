@echo off
rem Все параметры, скрипт с ошибочными строками и неверные запуски
rem Запуск: scripts\run_with_errors.bat (из любой папки)
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
%PYTHON% src/terminalus.py --script startup/with_errors.emu

echo.
echo === 4. Оба параметра ===
%PYTHON% src/terminalus.py --vfs data/disk.xml --script startup/with_errors.emu

echo.
echo === 5. Справка --help ===
%PYTHON% src/terminalus.py --help

echo.
echo === 6. Стартовый скрипт не найден ===
%PYTHON% src/terminalus.py --script startup/not_exists.emu
echo Код возврата: %errorlevel%

echo.
echo === 7. Неизвестный параметр ===
%PYTHON% src/terminalus.py --unknown
echo Код возврата: %errorlevel%

echo.
echo === 8. Параметр --vfs без значения ===
%PYTHON% src/terminalus.py --vfs
echo Код возврата: %errorlevel%

endlocal
