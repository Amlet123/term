#!/bin/sh
# Три варианта VFS и некорректные файлы VFS (коды возврата)
# Запуск: sh scripts/run_vfs_errors.sh (из любой папки)

PYTHON="${PYTHON:-python3}"
cd "$(dirname "$0")/.." || exit 1
EMU_OUT_DIR="$(mktemp -d)"
export EMU_OUT_DIR
trap 'rm -rf "$EMU_OUT_DIR"' EXIT
export EMU_DEMO_DIR=/opt/demo

emu() {
    "$PYTHON" src/terminalus.py "$@"
}

for v in minimal several_files deep_tree; do
    echo ""
    echo "=== VFS: $v ==="
    emu --vfs "vfs_samples/$v.xml" --script startup/stage3_all.emu
done

echo ""
echo "=== Некорректные файлы VFS (ожидается код 3) ==="
for f in vfs_samples/invalid/*.xml; do
    echo ""
    echo "--- $f ---"
    emu --vfs "$f"
    echo "Код возврата: $?"
done

echo ""
echo "=== Файл VFS не найден (ожидается код 3) ==="
emu --vfs vfs_samples/not_exists.xml
echo "Код возврата: $?"
