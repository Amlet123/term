"""Тесты модуля terminalus: параметры, парсер, скрипты, запуск."""

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import commands
import terminalus
import vfs
from tests.helpers import TempDirTestCase, capture, make_session

PROMPT = "(vfs) user@host:/$ "
SAMPLE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<vfs><dir name="d"><file name="f.txt">x</file></dir></vfs>'
)


class SplitTokensTests(unittest.TestCase):
    """Проверки разбиения строки на слова."""

    def test_plain_words(self):
        """Слова делятся по пробелам."""
        self.assertEqual(terminalus.split_tokens("a  b c"), ["a", "b", "c"])

    def test_quotes_keep_spaces(self):
        """Кавычки позволяют пробелы внутри слова."""
        self.assertEqual(
            terminalus.split_tokens("ls \"a b\" 'c d' e"),
            ["ls", "a b", "c d", "e"],
        )

    def test_empty_quotes_give_empty_word(self):
        """Пустые кавычки дают пустое слово."""
        self.assertEqual(terminalus.split_tokens('x ""'), ["x", ""])

    def test_unclosed_quote_is_plain_text(self):
        """Незакрытая кавычка остаётся частью слова."""
        self.assertEqual(terminalus.split_tokens('x "ab'), ["x", '"ab'])


class ParseLineTests(unittest.TestCase):
    """Проверки разбора строки ввода."""

    def test_splits_command_and_args(self):
        """Строка делится на команду и аргументы."""
        self.assertEqual(
            terminalus.parse_line("ls -l /tmp"), ("ls", ["-l", "/tmp"])
        )

    def test_empty_and_comment_lines(self):
        """Пустая строка и комментарий дают пустую команду."""
        self.assertEqual(terminalus.parse_line("   "), ("", []))
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

    def test_expanded_value_with_spaces_in_quotes(self):
        """Значение с пробелами в кавычках остаётся одним словом."""
        with mock.patch.dict(os.environ, {"EMU_SPACED": "a b"}):
            self.assertEqual(
                terminalus.parse_line('cd "$EMU_SPACED/c"'), ("cd", ["a b/c"])
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
    """Проверки выполнения строк."""

    def test_runs_command(self):
        """Известная команда выполняется."""
        output = terminalus.execute(make_session(), "ls -l")
        self.assertIn("readme.txt", output)

    def test_unknown_command(self):
        """Неизвестная команда сообщает об ошибке с её именем."""
        with self.assertRaisesRegex(commands.CommandError, "foo"):
            terminalus.execute(make_session(), "foo bar")

    def test_empty_line_does_nothing(self):
        """Пустая строка ничего не выводит."""
        self.assertIsNone(terminalus.execute(make_session(), ""))

    def test_exit(self):
        """Команда exit сигнализирует о завершении."""
        with self.assertRaises(commands.ExitRequestedError):
            terminalus.execute(make_session(), "exit")

    def test_history_records_commands(self):
        """Выполненные строки, в том числе ошибочные, попадают в историю."""
        session = make_session()
        for line in ("ls", "", "# заметка", "cd docs"):
            terminalus.execute(session, line)
        with self.assertRaises(commands.CommandError):
            terminalus.execute(session, "foo")
        self.assertEqual(session.history, ["ls", "cd docs", "foo"])

    def test_history_command_lists_itself(self):
        """Команда history видит сама себя в истории."""
        session = make_session()
        terminalus.execute(session, "ls")
        output = terminalus.execute(session, "history")
        self.assertEqual(output.split("\n")[-1], "    2  history")


class ReplTests(unittest.TestCase):
    """Проверки интерактивного цикла."""

    def run_repl(self, lines):
        """Запускает REPL на заданных вводах и возвращает вывод."""
        with mock.patch("builtins.input", side_effect=lines):
            return capture(terminalus.repl, make_session())[1]

    def test_full_session(self):
        """Сессия с командой, ошибкой и выходом печатает всё нужное."""
        output = self.run_repl(["ls -l", "foo", "exit"])
        self.assertIn("readme.txt", output)
        self.assertIn("Ошибка: неизвестная команда 'foo'", output)
        self.assertIn("Завершение работы эмулятора.", output)

    def test_eof_ends_session(self):
        """Ctrl+D завершает работу без сообщения об ошибке."""
        self.assertNotIn("Ошибка", self.run_repl([EOFError()]))

    def test_banner_lists_all_commands(self):
        """Приветствие содержит пользователя, хост и все команды."""
        banner = terminalus.make_banner("alice", "box")
        self.assertIn("alice@box", banner)
        for name in commands.COMMANDS:
            self.assertIn(name, banner)


class ArgsTests(unittest.TestCase):
    """Проверки параметров командной строки."""

    def test_no_args(self):
        """Без параметров оба пути не заданы."""
        self.assertEqual(terminalus.parse_args([]), terminalus.Config())

    def test_both_args(self):
        """Параметры --vfs и --script попадают в конфигурацию."""
        config = terminalus.parse_args(["--vfs", "d.xml", "--script", "s.emu"])
        self.assertEqual(config.vfs_path, "d.xml")
        self.assertEqual(config.script_path, "s.emu")

    def test_invalid_args_exit_with_code_2(self):
        """Неизвестный параметр, сокращение и пропущенное значение."""
        for argv in (["--bad"], ["--vf", "x"], ["--vfs"], ["extra"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as context:
                        terminalus.parse_args(argv)
                self.assertEqual(context.exception.code, 2)


class InfoTests(unittest.TestCase):
    """Проверки имени VFS и отладочного вывода."""

    def test_vfs_name(self):
        """Имя VFS это последний элемент пути, по умолчанию vfs."""
        self.assertEqual(terminalus.get_vfs_name("data/disk.xml"), "disk.xml")
        self.assertEqual(terminalus.get_vfs_name("data/dir/"), "dir")
        self.assertEqual(terminalus.get_vfs_name(None), "vfs")
        self.assertEqual(terminalus.get_vfs_name(""), "vfs")

    def test_format_config_shows_params(self):
        """Отладочный вывод показывает заданные и незаданные параметры."""
        text = terminalus.format_config(terminalus.Config("a.xml", None))
        self.assertIn("a.xml", text)
        self.assertEqual(text.count(terminalus.NOT_SET), 1)

    def test_format_vfs_info(self):
        """Строка о VFS содержит число каталогов и файлов."""
        text = terminalus.format_vfs_info(make_session().root)
        self.assertIn("каталогов 3, файлов 4", text)


class ScriptTestCase(TempDirTestCase):
    """Основа для тестов со скриптами и файлами VFS."""

    def write_script(self, text, encoding="utf-8"):
        """Записывает файл скрипта и возвращает путь к нему."""
        return self.write_file(text, "script.emu", encoding)


class ReadScriptTests(ScriptTestCase):
    """Проверки чтения стартового скрипта."""

    def test_bom_and_crlf_are_handled(self):
        """BOM и переводы строк Windows не попадают в строки."""
        path = self.write_script("ls\r\ncd a\r\n", "utf-8-sig")
        self.assertEqual(terminalus.read_script(path), ["ls", "cd a"])

    def test_missing_file(self):
        """Отсутствующий файл приводит к ScriptError."""
        path = os.path.join(self.make_folder(), "none.emu")
        with self.assertRaises(terminalus.ScriptError):
            terminalus.read_script(path)

    def test_wrong_encoding(self):
        """Файл не в UTF-8 приводит к ScriptError."""
        path = self.write_script("ls\n", "utf-16")
        with self.assertRaises(terminalus.ScriptError):
            terminalus.read_script(path)


class RunScriptTests(unittest.TestCase):
    """Проверки выполнения строк скрипта."""

    def run_lines(self, lines):
        """Выполняет строки и возвращает пару (был ли exit, вывод)."""
        return capture(terminalus.run_script, make_session(), lines)

    def test_shows_input_and_output(self):
        """Скрипт показывает и ввод, и вывод, как диалог."""
        done, output = self.run_lines(["ls -l"])
        self.assertFalse(done)
        self.assertIn(PROMPT + "ls -l", output)
        self.assertIn("readme.txt", output)

    def test_errors_are_reported_and_skipped(self):
        """Ошибочные строки сообщают об ошибке, остальные выполняются."""
        _, output = self.run_lines(["foo", "cd a b", "ls"])
        self.assertIn("Ошибка (строка 1): неизвестная команда", output)
        self.assertIn("Ошибка (строка 2): cd: слишком много", output)
        self.assertIn("readme.txt", output)

    def test_exit_stops_script(self):
        """После exit остальные строки не выполняются."""
        done, output = self.run_lines(["exit", "ls"])
        self.assertTrue(done)
        self.assertNotIn("readme.txt", output)

    def test_prompt_follows_cd_in_script(self):
        """Приглашение в диалоге скрипта показывает текущий каталог."""
        _, output = self.run_lines(["cd docs", "ls"])
        self.assertIn("(vfs) user@host:/docs$ ls", output)

    def test_blank_and_comment_lines_are_not_shown(self):
        """Пустые строки и комментарии не показываются и не выполняются."""
        _, output = self.run_lines(["", "   ", "# заметка", "ls"])
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
        path = self.write_script("cd /\n")
        code, out, _ = self.run_main(["--script", path], ["exit"])
        self.assertEqual(code, terminalus.EXIT_OK)
        self.assertIn("Завершение работы эмулятора.", out)

    def test_missing_script_is_reported(self):
        """Отсутствующий скрипт: сообщение в stderr и код 1."""
        path = os.path.join(self.make_folder(), "none.emu")
        code, _, err = self.run_main(["--script", path])
        self.assertEqual(code, terminalus.EXIT_SCRIPT_ERROR)
        self.assertIn("Ошибка", err)

    def test_vfs_is_loaded_and_named(self):
        """VFS загружается из XML, имя берётся из пути."""
        vfs_path = self.write_file(SAMPLE_XML, "disk.xml")
        script = self.write_script("ls\nexit\n")
        code, out, _ = self.run_main(["--vfs", vfs_path, "--script", script])
        self.assertEqual(code, terminalus.EXIT_OK)
        self.assertIn("каталогов 1, файлов 1", out)
        self.assertIn("(disk.xml) ", out)

    def test_without_vfs_memory_is_empty(self):
        """Без --vfs создаётся пустая VFS."""
        path = self.write_script("exit\n")
        _, out, _ = self.run_main(["--script", path])
        self.assertIn("каталогов 0, файлов 0", out)

    def test_broken_vfs_is_reported(self):
        """Повреждённый файл VFS: сообщение в stderr и код 3."""
        path = self.write_file("<vfs><file")
        code, _, err = self.run_main(["--vfs", path])
        self.assertEqual(code, terminalus.EXIT_VFS_ERROR)
        self.assertIn("Ошибка", err)

    def test_missing_vfs_is_reported(self):
        """Отсутствующий файл VFS: код 3."""
        path = os.path.join(self.make_folder(), "none.xml")
        code, _, _ = self.run_main(["--vfs", path])
        self.assertEqual(code, terminalus.EXIT_VFS_ERROR)

    def test_vfs_save_from_script(self):
        """vfs-save из стартового скрипта создаёт файл с копией VFS."""
        vfs_path = self.write_file(SAMPLE_XML, "disk.xml")
        target = os.path.join(self.make_folder(), "copy.xml")
        script = self.write_script(f'vfs-save "{target}"\nexit\n')
        self.run_main(["--vfs", vfs_path, "--script", script])
        self.assertEqual(vfs.count_nodes(vfs.load_vfs(target)), (1, 1))


if __name__ == "__main__":
    unittest.main()
