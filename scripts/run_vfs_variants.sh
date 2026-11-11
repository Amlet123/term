#!/bin/sh
# Три варианта VFS: минимальный, несколько файлов, глубокое дерево
# Запуск: sh scripts/run_vfs_variants.sh (из любой папки)

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
