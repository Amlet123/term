"""Тесты модуля commands: сеанс и команды этапа 3."""

import os
import unittest

import commands
import vfs
from tests.helpers import TempDirTestCase, make_session, snapshot


class SessionTests(unittest.TestCase):
    """Проверки сеанса."""

    def test_prompt_contains_vfs_name(self):
        """Приглашение содержит имя VFS, пользователя и хост."""
        session = commands.Session(vfs.new_root(), "myvfs", "alice", "box")
        self.assertEqual(session.prompt(), "(myvfs) alice@box:~$ ")


class StubTests(unittest.TestCase):
    """Проверки команд-заглушек."""

    def test_ls_prints_name_and_args(self):
        """Заглушка ls выводит своё имя и аргументы."""
        output = commands.cmd_ls(make_session(), ["-l", "/tmp"])
        self.assertIn("команда: ls", output)
        self.assertIn("['-l', '/tmp']", output)

    def test_cd_prints_name_and_args(self):
        """Заглушка cd выводит своё имя и аргументы."""
        output = commands.cmd_cd(make_session(), ["/home"])
        self.assertIn("команда: cd", output)
        self.assertIn("['/home']", output)

    def test_cd_too_many_args(self):
        """cd с несколькими аргументами сообщает об ошибке."""
        with self.assertRaises(commands.CommandError):
            commands.cmd_cd(make_session(), ["a", "b"])


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

    def test_registered(self):
        """Команда зарегистрирована под именем vfs-save."""
        self.assertIn("vfs-save", commands.COMMANDS)


if __name__ == "__main__":
    unittest.main()
