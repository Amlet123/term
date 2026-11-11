@echo off
rem rmdir: изменения VFS сохраняются и видны после перезагрузки
rem Запуск: scripts\run_rmdir.bat (из любой папки)
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
echo === Этап 5: rmdir на vfs_samples/rmdir_demo.xml ===
%PYTHON% src/terminalus.py --vfs vfs_samples/rmdir_demo.xml --script startup/stage5_all.emu

echo.
echo === Повторная загрузка VFS, сохранённой после rmdir ===
%PYTHON% src/terminalus.py --vfs "%EMU_OUT_DIR%/after_rmdir.xml" --script startup/stage5_check.emu

rmdir /s /q "%EMU_OUT_DIR%"
endlocal
