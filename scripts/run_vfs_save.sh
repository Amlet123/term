#!/bin/sh
# Круговая проверка vfs-save на трёх вариантах VFS
# Запуск: sh scripts/run_vfs_save.sh (из любой папки)

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
    echo "=== Круговая проверка VFS: $v ==="
    emu --vfs "vfs_samples/$v.xml" --script startup/save_copy1.emu
    emu --vfs "$EMU_OUT_DIR/copy1.xml" --script startup/save_copy2.emu
    if cmp -s "$EMU_OUT_DIR/copy1.xml" "$EMU_OUT_DIR/copy2.xml"; then
        echo "Результат: сохранённые копии совпадают"
    else
        echo "Результат: КОПИИ РАЗЛИЧАЮТСЯ"
    fi
done
