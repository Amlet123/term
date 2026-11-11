#!/bin/sh
# Все параметры, скрипт с ошибочными строками и неверные запуски
# Запуск: sh scripts/run_with_errors.sh (из любой папки)

PYTHON="${PYTHON:-python3}"
cd "$(dirname "$0")/.." || exit 1
EMU_OUT_DIR="$(mktemp -d)"
export EMU_OUT_DIR
trap 'rm -rf "$EMU_OUT_DIR"' EXIT
export EMU_DEMO_DIR=/opt/demo

emu() {
    "$PYTHON" src/terminalus.py "$@"
}

echo ""
echo "=== 1. Без параметров (команды через stdin) ==="
echo exit | emu

echo ""
echo "=== 2. Только --vfs ==="
echo exit | emu --vfs vfs_samples/minimal.xml

echo ""
echo "=== 3. Только --script ==="
emu --script startup/with_errors.emu

echo ""
echo "=== 4. Оба параметра ==="
emu --vfs vfs_samples/minimal.xml --script startup/with_errors.emu

echo ""
echo "=== 5. Справка --help ==="
emu --help

echo ""
echo "=== 6. Стартовый скрипт не найден ==="
emu --script startup/not_exists.emu
echo "Код возврата: $?"

echo ""
echo "=== 7. Неизвестный параметр ==="
emu --unknown
echo "Код возврата: $?"

echo ""
echo "=== 8. Параметр --vfs без значения ==="
emu --vfs
echo "Код возврата: $?"
