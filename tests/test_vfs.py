"""Тесты модуля vfs: дерево, пути, загрузка и сохранение XML."""

import os
import unittest

import vfs
from tests.helpers import BINARY_DATA, TempDirTestCase, make_tree, snapshot

HEADER = '<?xml version="1.0" encoding="UTF-8"?>'


def wrap(body: str) -> str:
    """Оборачивает содержимое в корневой элемент VFS."""
    return f"{HEADER}<vfs>{body}</vfs>"


class TreeTests(unittest.TestCase):
    """Проверки дерева и разбора путей."""

    def setUp(self):
        """Создаёт тестовое дерево."""
        self.root = make_tree()
        self.guide = vfs.resolve(self.root, self.root, "docs/guide")

    def test_node_path(self):
        """Путь узла строится от корня."""
        self.assertEqual(vfs.node_path(self.root), "/")
        self.assertEqual(vfs.node_path(self.guide), "/docs/guide")

    def test_resolve_absolute_and_relative(self):
        """Абсолютный и относительный пути ведут к одному узлу."""
        docs = vfs.resolve(self.root, self.root, "/docs")
        self.assertIs(vfs.resolve(self.root, docs, "guide"), self.guide)
        self.assertIs(vfs.resolve(self.root, docs, "/docs/guide"), self.guide)

    def test_resolve_dots(self):
        """Точки и повторные разделители игнорируются, .. ведёт вверх."""
        node = vfs.resolve(self.root, self.guide, "./..//guide/../..")
        self.assertIs(node, self.root)

    def test_parent_of_root_is_root(self):
        """Выше корня подняться нельзя."""
        self.assertIs(vfs.resolve(self.root, self.root, "../.."), self.root)

    def test_resolve_missing(self):
        """Отсутствующий путь приводит к VfsError."""
        with self.assertRaises(vfs.VfsError):
            vfs.resolve(self.root, self.root, "nope")

    def test_resolve_through_file(self):
        """Путь через файл как через каталог приводит к VfsError."""
        with self.assertRaises(vfs.VfsError):
            vfs.resolve(self.root, self.root, "readme.txt/x")

    def test_add_child_rejects_bad_names(self):
        """Пустое имя, имя с / и точки недопустимы."""
        for name in ("", "a/b", ".", ".."):
            with self.subTest(name=name):
                with self.assertRaises(vfs.VfsError):
                    vfs.add_file(self.root, name)

    def test_add_child_rejects_duplicate(self):
        """Повторное имя в каталоге недопустимо."""
        with self.assertRaises(vfs.VfsError):
            vfs.add_dir(self.root, "docs")

    def test_count_nodes(self):
        """Подсчёт не включает корень."""
        self.assertEqual(vfs.count_nodes(self.root), (3, 4))
        self.assertEqual(vfs.count_nodes(vfs.new_root()), (0, 0))


class LoadTests(TempDirTestCase):
    """Проверки загрузки VFS из XML."""

    def load(self, body: str):
        """Записывает XML во временный файл и загружает его."""
        return vfs.load_vfs(self.write_file(wrap(body)))

    def test_loads_dirs_and_files(self):
        """Каталоги, файлы и их содержимое попадают в память."""
        root = self.load(
            '<dir name="a"><file name="x.txt">hi</file></dir>'
            '<file name="y.bin" encoding="base64">AAEC/w==</file>'
        )
        self.assertEqual(
            snapshot(root),
            {
                "a": {"x.txt": (b"hi", "text")},
                "y.bin": (BINARY_DATA, "base64"),
            },
        )

    def test_base64_may_contain_whitespace(self):
        """Пробелы и переводы строк внутри base64 допустимы."""
        root = self.load('<file name="b" encoding="base64">AAEC\n /w==</file>')
        self.assertEqual(root.children["b"].content, BINARY_DATA)

    def test_empty_file_and_empty_dir(self):
        """Пустые элементы дают пустой файл и пустой каталог."""
        root = self.load('<file name="f"/><dir name="d"/>')
        self.assertEqual(root.children["f"].content, b"")
        self.assertTrue(root.children["d"].is_dir)

    def test_invalid_documents(self):
        """Каждое нарушение формата приводит к VfsError."""
        bodies = {
            "unknown tag": '<link name="x"/>',
            "no name": "<file>x</file>",
            "bad base64": '<file name="x" encoding="base64">!!</file>',
            "bad encoding": '<file name="x" encoding="rot13">a</file>',
            "duplicate": '<file name="a"/><file name="a"/>',
            "bad name": '<file name="a/b"/>',
        }
        for title, body in bodies.items():
            with self.subTest(title):
                with self.assertRaises(vfs.VfsError):
                    self.load(body)

    def test_not_xml(self):
        """Файл, не являющийся XML, приводит к VfsError."""
        with self.assertRaises(vfs.VfsError):
            vfs.load_vfs(self.write_file("<vfs><file"))

    def test_wrong_root_tag(self):
        """Неверный корневой элемент приводит к VfsError."""
        with self.assertRaises(vfs.VfsError):
            vfs.load_vfs(self.write_file(f"{HEADER}<root/>"))

    def test_missing_file(self):
        """Отсутствующий файл приводит к VfsError."""
        path = os.path.join(self.make_folder(), "none.xml")
        with self.assertRaises(vfs.VfsError):
            vfs.load_vfs(path)


class SaveTests(TempDirTestCase):
    """Проверки сохранения VFS в XML."""

    def test_round_trip(self):
        """Сохранённая и заново загруженная VFS совпадает с исходной."""
        root = make_tree()
        path = os.path.join(self.make_folder(), "saved.xml")
        vfs.save_vfs(root, path)
        self.assertEqual(snapshot(vfs.load_vfs(path)), snapshot(root))

    def test_second_save_is_identical(self):
        """Повторное сохранение даёт тот же файл."""
        folder = self.make_folder()
        first = os.path.join(folder, "first.xml")
        second = os.path.join(folder, "second.xml")
        vfs.save_vfs(make_tree(), first)
        vfs.save_vfs(vfs.load_vfs(first), second)
        with open(first, "rb") as one, open(second, "rb") as two:
            self.assertEqual(one.read(), two.read())

    def test_binary_stays_base64(self):
        """Двоичные данные в файле остаются в формате base64."""
        path = os.path.join(self.make_folder(), "saved.xml")
        vfs.save_vfs(make_tree(), path)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('encoding="base64"', text)
        self.assertIn("AAEC/w==", text)

    def test_save_to_missing_folder(self):
        """Сохранение в несуществующую папку приводит к VfsError."""
        path = os.path.join(self.make_folder(), "no_dir", "saved.xml")
        with self.assertRaises(vfs.VfsError):
            vfs.save_vfs(make_tree(), path)


if __name__ == "__main__":
    unittest.main()
