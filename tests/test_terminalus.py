"""Тесты этапов 1 и 2: парсер, команды, параметры, скрипты, REPL."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from src import terminalus

PROMPT = "(vfs) user@host:~$ "


def capture(function, *args):
    """Вызывает функцию и возвращает пару (результат, вывод в stdout)."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = function(*args)
    return result, buffer.getvalue()


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

    def test_comment_line(self):
        """Строка, начинающаяся с #, считается комментарием."""
        self.assertEqual(terminalus.parse_line("  # заметка"), ("", []))

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
        with self.assertRaises(terminalus.ExitRequestedError):
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
    """Проверки интерактивного цикла и приглашения."""

    def run_repl(self, lines):
        """Запускает REPL на заданных вводах и возвращает вывод."""
        with mock.patch("builtins.input", side_effect=lines):
            return capture(terminalus.repl, "> ")[1]

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


class ArgsTests(unittest.TestCase):
    """Проверки параметров командной строки."""

    def test_no_args(self):
        """Без параметров оба пути не заданы."""
        self.assertEqual(terminalus.parse_args([]), terminalus.Config())

    def test_both_args(self):
        """Параметры --vfs и --script попадают в конфигурацию."""
        config = terminalus.parse_args(
            ["--vfs", "d/disk.xml", "--script", "s.emu"]
        )
        self.assertEqual(config.vfs_path, "d/disk.xml")
        self.assertEqual(config.script_path, "s.emu")

    def test_invalid_args_exit_with_code_2(self):
        """Неизвестный параметр, сокращение и пропущенное значение."""
        for argv in (["--bad"], ["--vf", "x"], ["--vfs"], ["extra"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as context:
                        terminalus.parse_args(argv)
                self.assertEqual(context.exception.code, 2)


class VfsNameTests(unittest.TestCase):
    """Проверки имени VFS для приглашения."""

    def test_name_is_last_path_element(self):
        """Имя VFS это последний элемент пути."""
        self.assertEqual(terminalus.get_vfs_name("data/disk.xml"), "disk.xml")
        self.assertEqual(terminalus.get_vfs_name("data/dir/"), "dir")

    def test_default_name(self):
        """Без пути используется имя по умолчанию."""
        self.assertEqual(terminalus.get_vfs_name(None), "vfs")
        self.assertEqual(terminalus.get_vfs_name(""), "vfs")


class FormatConfigTests(unittest.TestCase):
    """Проверки отладочного вывода параметров."""

    def test_shows_given_params(self):
        """В отладочном выводе видны оба заданных пути."""
        text = terminalus.format_config(terminalus.Config("a.xml", "b.emu"))
        self.assertIn("a.xml", text)
        self.assertIn("b.emu", text)

    def test_shows_unset_params(self):
        """Незаданные параметры помечаются как не заданные."""
        text = terminalus.format_config(terminalus.Config())
        self.assertEqual(text.count(terminalus.NOT_SET), 2)


class ScriptTestCase(unittest.TestCase):
    """Основа для тестов, которым нужны временные файлы."""

    def setUp(self):
        """Создаёт временную папку для файлов скриптов."""
        self.folder_object = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder_object.cleanup)
        self.folder = self.folder_object.name

    def write_script(self, text, encoding="utf-8"):
        """Записывает файл скрипта и возвращает путь к нему."""
        path = os.path.join(self.folder, "script.emu")
        with open(path, "w", encoding=encoding, newline="") as script_file:
            script_file.write(text)
        return path


class ReadScriptTests(ScriptTestCase):
    """Проверки чтения стартового скрипта."""

    def test_bom_and_crlf_are_handled(self):
        """BOM и переводы строк Windows не попадают в строки."""
        path = self.write_script("ls\r\ncd a\r\n", "utf-8-sig")
        self.assertEqual(terminalus.read_script(path), ["ls", "cd a"])

    def test_missing_file(self):
        """Отсутствующий файл приводит к ScriptError."""
        path = os.path.join(self.folder, "none.emu")
        with self.assertRaises(terminalus.ScriptError):
            terminalus.read_script(path)

    def test_wrong_encoding(self):
        """Файл не в UTF-8 приводит к ScriptError."""
        path = self.write_script("ls\n", "utf-16")
        with self.assertRaises(terminalus.ScriptError):
            terminalus.read_script(path)


class RunScriptTests(unittest.TestCase):
    """Проверки выполнения строк скрипта."""

    def test_shows_input_and_output(self):
        """Скрипт показывает и ввод, и вывод, как диалог."""
        done, output = capture(terminalus.run_script, ["ls -l"], PROMPT)
        self.assertFalse(done)
        self.assertIn(PROMPT + "ls -l", output)
        self.assertIn("['-l']", output)

    def test_errors_are_reported_and_skipped(self):
        """Ошибочные строки сообщают об ошибке, остальные выполняются."""
        lines = ["foo", "cd a b", "ls"]
        done, output = capture(terminalus.run_script, lines, PROMPT)
        self.assertFalse(done)
        self.assertIn("Ошибка (строка 1): неизвестная команда", output)
        self.assertIn("Ошибка (строка 2): cd: слишком много", output)
        self.assertIn("команда: ls", output)

    def test_exit_stops_script(self):
        """После exit остальные строки не выполняются."""
        done, output = capture(terminalus.run_script, ["exit", "ls"], PROMPT)
        self.assertTrue(done)
        self.assertNotIn("команда: ls", output)

    def test_blank_and_comment_lines_are_not_shown(self):
        """Пустые строки и комментарии не показываются и не выполняются."""
        lines = ["", "   ", "# заметка", "ls"]
        _, output = capture(terminalus.run_script, lines, PROMPT)
        self.assertNotIn("заметка", output)
        self.assertEqual(output.count(PROMPT), 1)


class MainTests(ScriptTestCase):
    """Проверки запуска целиком."""

    def run_main(self, argv, inputs=()):
        """Запускает main и возвращает код, stdout и stderr."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("builtins.input", side_effect=list(inputs)):
            with redirect_stdout(out), redirect_stderr(err):
                code = terminalus.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_script_with_exit_skips_repl(self):
        """Скрипт с exit завершает работу, REPL не запускается."""
        path = self.write_script("ls\nexit\n")
        code, out, _ = self.run_main(["--script", path])
        self.assertEqual(code, terminalus.EXIT_OK)
        self.assertIn("[отладка]", out)
        self.assertIn("Завершение работы эмулятора.", out)

    def test_repl_starts_after_script_without_exit(self):
        """Скрипт без exit передаёт управление интерактивному режиму."""
        path = self.write_script("ls\n")
        code, out, _ = self.run_main(["--script", path], ["exit"])
        self.assertEqual(code, terminalus.EXIT_OK)
        self.assertIn("команда: ls", out)
        self.assertIn("Завершение работы эмулятора.", out)

    def test_missing_script_is_reported(self):
        """Отсутствующий скрипт: сообщение в stderr и код 1."""
        path = os.path.join(self.folder, "none.emu")
        code, out, err = self.run_main(["--script", path])
        self.assertEqual(code, terminalus.EXIT_SCRIPT_ERROR)
        self.assertIn("Ошибка", err)
        self.assertIn("[отладка]", out)

    def test_prompt_uses_vfs_name(self):
        """Имя VFS из параметра --vfs попадает в приглашение."""
        path = self.write_script("ls\nexit\n")
        argv = ["--vfs", "data/disk.xml", "--script", path]
        _, out, _ = self.run_main(argv)
        self.assertIn("(disk.xml) ", out)
        self.assertIn("data/disk.xml", out)


if __name__ == "__main__":
    unittest.main()
