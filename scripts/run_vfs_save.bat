@echo off
rem Круговая проверка vfs-save на трёх вариантах VFS
rem Запуск: scripts\run_vfs_save.bat (из любой папки)
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
if not defined PYTHON set PYTHON=python
cd /d "%~dp0.."
set "EMU_OUT_DIR=%TEMP%\terminalus_out"
if exist "%EMU_OUT_DIR%" rmdir /s /q "%EMU_OUT_DIR%"
mkdir "%EMU_OUT_DIR%"
set "EMU_DEMO_DIR=C:\demo"

set "COPY1=%EMU_OUT_DIR%\copy1.xml"
set "COPY2=%EMU_OUT_DIR%\copy2.xml"
for %%V in (minimal several_files deep_tree) do (
    echo.
    echo === Круговая проверка VFS: %%V ===
    %PYTHON% src/terminalus.py --vfs vfs_samples/%%V.xml --script startup/save_copy1.emu
    %PYTHON% src/terminalus.py --vfs "%COPY1%" --script startup/save_copy2.emu
    fc /b "%COPY1%" "%COPY2%" >nul
    if errorlevel 1 (echo Результат: КОПИИ РАЗЛИЧАЮТСЯ) else (echo Результат: копии совпадают)
)

rmdir /s /q "%EMU_OUT_DIR%"
endlocal
