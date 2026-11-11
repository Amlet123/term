"""Общие вспомогательные средства для тестов."""

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from commands import Session
from vfs import BASE64, Node, add_dir, add_file, new_root

BINARY_DATA = b"\x00\x01\x02\xff"


def capture(function, *args):
    """Вызывает функцию и возвращает пару (результат, вывод в stdout)."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = function(*args)
    return result, buffer.getvalue()


def make_tree() -> Node:
    """Строит VFS для тестов и возвращает её корень."""
    root = new_root()
    docs = add_dir(root, "docs")
    guide = add_dir(docs, "guide")
    add_file(guide, "intro.txt", "привет".encode("utf-8"))
    add_file(docs, "notes.txt", b"note")
    add_file(root, "readme.txt", b"hi")
    add_file(root, "data.bin", BINARY_DATA, BASE64)
    add_dir(root, "empty")
    return root


def make_session() -> Session:
    """Создаёт сеанс с тестовой VFS."""
    return Session(make_tree(), "vfs", "user", "host")


def snapshot(node: Node):
    """Превращает дерево в вложенные словари для сравнения в тестах."""
    if node.is_dir:
        return {name: snapshot(child) for name, child in node.children.items()}
    return (node.content, node.encoding)


class TempDirTestCase(unittest.TestCase):
    """Основа для тестов, которым нужны временные файлы."""

    def make_folder(self) -> str:
        """Создаёт временную папку, удаляемую после теста."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        return folder

    def write_file(self, text, name="file.xml", encoding="utf-8") -> str:
        """Записывает файл во временную папку и возвращает его путь."""
        path = os.path.join(self.make_folder(), name)
        with open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        return path
