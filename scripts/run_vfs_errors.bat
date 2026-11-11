@echo off
rem Три варианта VFS и некорректные файлы VFS (коды возврата)
rem Запуск: scripts\run_vfs_errors.bat (из любой папки)
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
if not defined PYTHON set PYTHON=python
cd /d "%~dp0.."
set "EMU_OUT_DIR=%TEMP%\terminalus_out"
if exist "%EMU_OUT_DIR%" rmdir /s /q "%EMU_OUT_DIR%"
mkdir "%EMU_OUT_DIR%"
set "EMU_DEMO_DIR=C:\demo"

for %%V in (minimal several_files deep_tree) do (
    echo.
    echo === VFS: %%V ===
    %PYTHON% src/terminalus.py --vfs vfs_samples/%%V.xml --script startup/stage3_all.emu
)

echo.
echo === Некорректные файлы VFS - ожидается код 3 ===
for %%F in (vfs_samples\invalid\*.xml) do (
    echo.
    echo --- %%F ---
    %PYTHON% src/terminalus.py --vfs "%%F"
    call echo Код возврата: %%errorlevel%%
)

echo.
echo === Файл VFS не найден - ожидается код 3 ===
%PYTHON% src/terminalus.py --vfs vfs_samples/not_exists.xml
echo Код возврата: %errorlevel%

rmdir /s /q "%EMU_OUT_DIR%"
endlocal
