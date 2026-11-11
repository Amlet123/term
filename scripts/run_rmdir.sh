#!/bin/sh
# rmdir: изменения VFS сохраняются и видны после перезагрузки
# Запуск: sh scripts/run_rmdir.sh (из любой папки)

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
echo "=== Этап 5: rmdir на vfs_samples/rmdir_demo.xml ==="
emu --vfs vfs_samples/rmdir_demo.xml --script startup/stage5_all.emu

echo ""
echo "=== Повторная загрузка VFS, сохранённой после rmdir ==="
emu --vfs "$EMU_OUT_DIR/after_rmdir.xml" --script startup/stage5_check.emu
