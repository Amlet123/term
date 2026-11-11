"""Тесты модуля commands: сеанс и команды этапов 3 и 4."""

import io
import os
import unittest
from contextlib import redirect_stdout

import commands
import vfs
from tests.helpers import TempDirTestCase, make_session, snapshot


def lines(text):
    """Делит вывод команды на строки."""
    return text.split("\n")


class SessionTests(unittest.TestCase):
    """Проверки сеанса."""

    def test_prompt_shows_vfs_name_and_directory(self):
        """Приглашение содержит имя VFS и текущий каталог."""
        session = commands.Session(vfs.new_root(), "myvfs", "alice", "box")
        self.assertEqual(session.prompt(), "(myvfs) alice@box:/$ ")

    def test_prompt_follows_cd(self):
        """После cd приглашение показывает новый каталог."""
        session = make_session()
        commands.cmd_cd(session, ["docs/guide"])
        self.assertEqual(session.prompt(), "(vfs) user@host:/docs/guide$ ")


class CdTests(unittest.TestCase):
    """Проверки команды cd."""

    def setUp(self):
        """Создаёт сеанс с тестовой VFS."""
        self.session = make_session()

    def cd(self, *args):
        """Выполняет cd и возвращает путь текущего каталога."""
        self.assertIsNone(commands.cmd_cd(self.session, list(args)))
        return vfs.node_path(self.session.cwd)

    def test_absolute_and_relative(self):
        """cd понимает абсолютные и относительные пути."""
        self.assertEqual(self.cd("/docs"), "/docs")
        self.assertEqual(self.cd("guide"), "/docs/guide")
        self.assertEqual(self.cd("../.."), "/")

    def test_without_args_goes_to_root(self):
        """cd без аргументов переходит в корень."""
        self.cd("docs")
        self.assertEqual(self.cd(), "/")

    def test_errors_keep_directory(self):
        """Ошибочный cd не меняет текущий каталог."""
        self.cd("docs")
        for args in (["nope"], ["/readme.txt"], ["a", "b"]):
            with self.subTest(args=args):
                with self.assertRaises(commands.CommandError):
                    commands.cmd_cd(self.session, args)
                self.assertEqual(vfs.node_path(self.session.cwd), "/docs")

    def test_error_messages(self):
        """Сообщения называют команду и путь."""
        with self.assertRaisesRegex(commands.CommandError, "cd: nope"):
            commands.cmd_cd(self.session, ["nope"])
        with self.assertRaisesRegex(commands.CommandError, "не каталог"):
            commands.cmd_cd(self.session, ["readme.txt"])


class LsTests(unittest.TestCase):
    """Проверки команды ls."""

    def setUp(self):
        """Создаёт сеанс с тестовой VFS."""
        self.session = make_session()

    def ls(self, *args):
        """Выполняет ls и возвращает вывод."""
        return commands.cmd_ls(self.session, list(args))

    def test_lists_current_directory_sorted(self):
        """ls без аргументов показывает имена текущего каталога по алфавиту."""
        self.assertEqual(
            lines(self.ls()), ["data.bin", "docs", "empty", "readme.txt"]
        )

    def test_relative_to_current_directory(self):
        """Относительный путь отсчитывается от текущего каталога."""
        commands.cmd_cd(self.session, ["docs"])
        self.assertEqual(lines(self.ls()), ["guide", "notes.txt"])
        self.assertEqual(lines(self.ls("guide")), ["intro.txt"])

    def test_long_format(self):
        """Флаг -l показывает тип и размер в байтах."""
        self.assertEqual(
            lines(self.ls("-l")),
            [
                "-        4 data.bin",
                "d        - docs",
                "d        - empty",
                "-        2 readme.txt",
            ],
        )

    def test_file_argument(self):
        """Для файла выводится он сам под тем же именем, как задан путь."""
        self.assertEqual(self.ls("docs/notes.txt"), "docs/notes.txt")
        self.assertEqual(self.ls("-l", "readme.txt"), "-        2 readme.txt")

    def test_several_paths_have_headers(self):
        """При нескольких путях перед списком выводится заголовок."""
        self.assertEqual(
            self.ls("docs/guide", "empty"),
            "docs/guide:\nintro.txt\n\nempty:",
        )

    def test_empty_directory_prints_nothing(self):
        """Пустой каталог не даёт вывода."""
        self.assertIsNone(self.ls("empty"))

    def test_errors(self):
        """Неизвестный параметр и отсутствующий путь сообщают об ошибке."""
        for args in (["-x"], ["nope"], ["docs", "nope"]):
            with self.subTest(args=args):
                with self.assertRaises(commands.CommandError):
                    self.ls(*args)


class ClearTests(unittest.TestCase):
    """Проверки команды clear."""

    def test_prints_clear_sequence(self):
        """clear печатает управляющую последовательность очистки экрана."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = commands.cmd_clear(make_session(), [])
        self.assertIsNone(result)
        self.assertEqual(buffer.getvalue(), commands.CLEAR_SEQUENCE)

    def test_arguments_are_errors(self):
        """clear не принимает аргументов."""
        with self.assertRaises(commands.CommandError):
            commands.cmd_clear(make_session(), ["now"])


class HistoryTests(unittest.TestCase):
    """Проверки команды history."""

    def setUp(self):
        """Создаёт сеанс с готовой историей из трёх команд."""
        self.session = make_session()
        self.session.history.extend(["ls", "cd docs", "find"])

    def history(self, *args):
        """Выполняет history и возвращает вывод."""
        return commands.cmd_history(self.session, list(args))

    def test_numbered_list(self):
        """history показывает пронумерованный список команд."""
        self.assertEqual(
            lines(self.history()),
            ["    1  ls", "    2  cd docs", "    3  find"],
        )

    def test_last_n(self):
        """history N показывает последние N команд с их номерами."""
        self.assertEqual(
            lines(self.history("2")), ["    2  cd docs", "    3  find"]
        )
        self.assertEqual(len(lines(self.history("99"))), 3)
        self.assertIsNone(self.history("0"))

    def test_clear(self):
        """history -c очищает историю."""
        self.assertIsNone(self.history("-c"))
        self.assertEqual(self.session.history, [])
        self.assertIsNone(self.history())

    def test_errors(self):
        """Неверные и лишние аргументы сообщают об ошибке."""
        for args in (["x"], ["-5"], ["1", "2"], ["-c", "1"]):
            with self.subTest(args=args):
                with self.assertRaises(commands.CommandError):
                    self.history(*args)


class FindTests(unittest.TestCase):
    """Проверки команды find."""

    def setUp(self):
        """Создаёт сеанс с тестовой VFS."""
        self.session = make_session()

    def find(self, *args):
        """Выполняет find и возвращает вывод."""
        return commands.cmd_find(self.session, list(args))

    def test_default_walks_current_directory(self):
        """find без аргументов обходит текущий каталог, пути начинаются с ./"""
        self.assertEqual(
            lines(self.find()),
            [
                ".",
                "./data.bin",
                "./docs",
                "./docs/guide",
                "./docs/guide/intro.txt",
                "./docs/notes.txt",
                "./empty",
                "./readme.txt",
            ],
        )

    def test_paths_follow_the_given_prefix(self):
        """Пути в выводе строятся от заданного начала."""
        self.assertEqual(
            lines(self.find("/docs")),
            [
                "/docs",
                "/docs/guide",
                "/docs/guide/intro.txt",
                "/docs/notes.txt",
            ],
        )
        self.assertEqual(lines(self.find("docs/"))[:2], ["docs/", "docs/guide"])

    def test_name_pattern(self):
        """-name ищет по шаблону с * и ?."""
        self.assertEqual(
            lines(self.find("/", "-name", "*.txt")),
            ["/docs/guide/intro.txt", "/docs/notes.txt", "/readme.txt"],
        )
        self.assertEqual(self.find("-name", "readm?.txt"), "./readme.txt")

    def test_type_filter(self):
        """-type d оставляет каталоги, -type f файлы."""
        self.assertEqual(
            lines(self.find("docs", "-type", "d")), ["docs", "docs/guide"]
        )
        self.assertEqual(
            lines(self.find("docs", "-type", "f")),
            ["docs/guide/intro.txt", "docs/notes.txt"],
        )

    def test_name_and_type_together(self):
        """-name и -type действуют вместе."""
        self.assertEqual(
            self.find("/", "-type", "d", "-name", "e*"), "/empty"
        )

    def test_nothing_found(self):
        """Если ничего не найдено, вывода нет."""
        self.assertIsNone(self.find("-name", "*.zip"))

    def test_options_may_precede_path(self):
        """Путь можно указать после параметров."""
        output = self.find("-name", "notes.txt", "docs")
        self.assertEqual(output, "docs/notes.txt")

    def test_errors(self):
        """Неверные аргументы и отсутствующий путь сообщают об ошибке."""
        cases = [
            ["nope"],
            ["-depth"],
            ["-name"],
            ["-type"],
            ["-type", "x"],
            ["docs", "empty"],
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(commands.CommandError):
                    self.find(*args)


class ExitTests(unittest.TestCase):
    """Проверки команды exit."""

    def test_exit_requests_shutdown(self):
        """Команда exit сигнализирует о завершении."""
        with self.assertRaises(commands.ExitRequestedError):
            commands.cmd_exit(make_session(), [])

    def test_exit_with_args_is_error(self):
        """exit с аргументами сообщает об ошибке."""
        with self.assertRaises(commands.CommandError):
            commands.cmd_exit(make_session(), ["now"])


class VfsSaveTests(TempDirTestCase):
    """Проверки команды vfs-save."""

    def test_saves_vfs_to_disk(self):
        """vfs-save записывает VFS, которую можно загрузить обратно."""
        session = make_session()
        path = os.path.join(self.make_folder(), "saved.xml")
        output = commands.cmd_vfs_save(session, [path])
        self.assertIn(path, output)
        self.assertEqual(
            snapshot(vfs.load_vfs(path)), snapshot(session.root)
        )

    def test_requires_exactly_one_argument(self):
        """Без аргументов и с лишними аргументами команда сообщает об ошибке."""
        for args in ([], ["a.xml", "b.xml"]):
            with self.subTest(args=args):
                with self.assertRaises(commands.CommandError):
                    commands.cmd_vfs_save(make_session(), args)

    def test_unwritable_path(self):
        """Недоступный путь приводит к CommandError."""
        path = os.path.join(self.make_folder(), "no_dir", "saved.xml")
        with self.assertRaises(commands.CommandError):
            commands.cmd_vfs_save(make_session(), [path])

    def test_registered_commands(self):
        """Все команды этапов 1-4 зарегистрированы."""
        expected = {"ls", "cd", "exit", "vfs-save", "clear", "history", "find"}
        self.assertEqual(set(commands.COMMANDS), expected)


if __name__ == "__main__":
    unittest.main()
