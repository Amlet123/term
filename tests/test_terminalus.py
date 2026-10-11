"""Тесты этапа 1: парсер, команды-заглушки, обработка ошибок, REPL."""

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from src import terminalus


class ParseLineTests(unittest.TestCase):
    """Проверки разбора строки ввода."""

    def test_splits_command_and_args(self):
        """Строка делится на команду и аргументы по пробелам."""
        self.assertEqual(
            terminalus.parse_line("ls -l /tmp"), ("ls", ["-l", "/tmp"])
        )

    def test_extra_spaces_are_ignored(self):
        """Лишние пробелы между словами не создают пустых аргументов."""
        self.assertEqual(terminalus.parse_line("  cd   a  "), ("cd", ["a"]))

    def test_empty_line(self):
        """Пустая строка даёт пустую команду."""
        self.assertEqual(terminalus.parse_line("   "), ("", []))

    def test_expands_env_variable(self):
        """Переменные $VAR и ${VAR} заменяются значениями из ОС."""
        with mock.patch.dict(os.environ, {"EMU_TEST_DIR": "/data"}):
            self.assertEqual(
                terminalus.parse_line("cd $EMU_TEST_DIR"), ("cd", ["/data"])
            )
            self.assertEqual(
                terminalus.parse_line("ls ${EMU_TEST_DIR}/x"),
                ("ls", ["/data/x"]),
            )

    def test_variable_expanded_to_nothing(self):
        """Пустая переменная в начале строки не приводит к сбою."""
        with mock.patch.dict(os.environ, {"EMU_EMPTY": ""}):
            self.assertEqual(terminalus.parse_line("$EMU_EMPTY"), ("", []))

    def test_undefined_variable_stays_as_is(self):
        """Неопределённая переменная остаётся в тексте без изменений."""
        with mock.patch.dict(os.environ):
            os.environ.pop("EMU_UNDEFINED", None)
            self.assertEqual(
                terminalus.parse_line("ls $EMU_UNDEFINED"),
                ("ls", ["$EMU_UNDEFINED"]),
            )


class ExecuteTests(unittest.TestCase):
    """Проверки выполнения команд."""

    def test_ls_stub_prints_name_and_args(self):
        """Заглушка ls выводит своё имя и аргументы."""
        output = terminalus.execute("ls -l /tmp")
        self.assertIn("ls", output)
        self.assertIn("['-l', '/tmp']", output)

    def test_cd_stub_prints_name_and_args(self):
        """Заглушка cd выводит своё имя и аргументы."""
        output = terminalus.execute("cd /home")
        self.assertIn("cd", output)
        self.assertIn("['/home']", output)

    def test_cd_too_many_args(self):
        """cd с несколькими аргументами сообщает об ошибке."""
        with self.assertRaises(terminalus.CommandError):
            terminalus.execute("cd a b")

    def test_exit_requests_shutdown(self):
        """Команда exit сигнализирует о завершении."""
        with self.assertRaises(terminalus.ExitRequested):
            terminalus.execute("exit")

    def test_exit_with_args_is_error(self):
        """exit с аргументами сообщает об ошибке, а не завершает работу."""
        with self.assertRaises(terminalus.CommandError):
            terminalus.execute("exit now")

    def test_unknown_command(self):
        """Неизвестная команда сообщает об ошибке с её именем."""
        with self.assertRaisesRegex(terminalus.CommandError, "foo"):
            terminalus.execute("foo bar")

    def test_empty_line_does_nothing(self):
        """Пустая строка ничего не выводит."""
        self.assertIsNone(terminalus.execute(""))


class ReplTests(unittest.TestCase):
    """Проверки интерактивного цикла."""

    def run_repl(self, lines):
        """Запускает REPL на заданных вводах и возвращает вывод."""
        buffer = io.StringIO()
        with mock.patch("builtins.input", side_effect=lines):
            with redirect_stdout(buffer):
                terminalus.repl("> ")
        return buffer.getvalue()

    def test_full_session(self):
        """Сессия с командой, ошибкой и выходом печатает всё нужное."""
        output = self.run_repl(["ls -a", "foo", "exit"])
        self.assertIn("аргументы: ['-a']", output)
        self.assertIn("Ошибка: неизвестная команда 'foo'", output)
        self.assertIn("Завершение работы эмулятора.", output)

    def test_eof_ends_session(self):
        """Ctrl+D завершает работу без сообщения об ошибке."""
        output = self.run_repl([EOFError()])
        self.assertNotIn("Ошибка", output)

    def test_prompt_contains_vfs_name(self):
        """Приглашение содержит имя VFS, пользователя и хост."""
        prompt = terminalus.make_prompt("myvfs", "alice", "box")
        self.assertEqual(prompt, "(myvfs) alice@box:~$ ")

    def test_banner_lists_all_commands(self):
        """Приветствие содержит пользователя, хост и все команды."""
        banner = terminalus.make_banner("alice", "box")
        self.assertIn("alice@box", banner)
        for name in terminalus.COMMANDS:
            self.assertIn(name, banner)


if __name__ == "__main__":
    unittest.main()
