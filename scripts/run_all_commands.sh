#!/bin/sh
# Все параметры со скриптом startup/all_commands.emu
# Запуск: sh scripts/run_all_commands.sh (из любой папки)

PYTHON="${PYTHON:-python3}"
cd "$(dirname "$0")/.." || exit 1
export EMU_DEMO_DIR=/opt/demo

emu() {
    "$PYTHON" src/terminalus.py "$@"
}

echo ""
echo "=== 1. Без параметров (команды через stdin) ==="
echo exit | emu

echo ""
echo "=== 2. Только --vfs ==="
echo exit | emu --vfs data/disk.xml

echo ""
echo "=== 3. Только --script ==="
emu --script startup/all_commands.emu

echo ""
echo "=== 4. Оба параметра ==="
emu --vfs data/disk.xml --script startup/all_commands.emu

echo ""
echo "=== 5. Справка --help ==="
emu --help
