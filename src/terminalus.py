"""Эмулятор оболочки UNIX-подобной ОС. Этап 3: виртуальная файловая система."""

import argparse
import getpass
import os
import re
import socket
import sys
from dataclasses import dataclass
from typing import Optional

from commands import COMMANDS, CommandError, ExitRequestedError, Session
from vfs import Node, VfsError, count_nodes, load_vfs, new_root

DEFAULT_VFS_NAME = "vfs"
DEFAULT_USER = "user"
COMMENT_PREFIX = "#"
NOT_SET = "(не задан)"
SCRIPT_ENCODING = "utf-8-sig"
TOKEN_PATTERN = re.compile(r"\"([^\"]*)\"|'([^']*)'|(\S+)")
EXIT_OK = 0
EXIT_SCRIPT_ERROR = 1
EXIT_VFS_ERROR = 3


@dataclass
class Config:
    """Параметры запуска эмулятора, заданные в командной строке."""

    vfs_path: Optional[str] = None
    script_path: Optional[str] = None


class ScriptError(Exception):
    """Стартовый скрипт невозможно прочитать."""


def parse_args(argv: Optional[list[str]] = None) -> Config:
    """Разбирает параметры командной строки.

    При неверных параметрах argparse печатает подсказку и завершает
    программу с кодом 2.
    """
    parser = argparse.ArgumentParser(
        prog="terminalus",
        description="Эмулятор оболочки UNIX-подобной ОС.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--vfs", metavar="ПУТЬ", help="путь к XML-файлу с содержимым VFS"
    )
    parser.add_argument(
        "--script", metavar="ПУТЬ", help="путь к стартовому скрипту"
    )
    args = parser.parse_args(argv)
    return Config(vfs_path=args.vfs, script_path=args.script)


def get_vfs_name(vfs_path: Optional[str]) -> str:
    """Возвращает имя VFS для приглашения: последний элемент пути."""
    if not vfs_path:
        return DEFAULT_VFS_NAME
    name = os.path.basename(os.path.normpath(vfs_path))
    return name or DEFAULT_VFS_NAME


def format_config(config: Config) -> str:
    """Формирует отладочный вывод всех параметров запуска."""
    vfs = NOT_SET if config.vfs_path is None else config.vfs_path
    script = NOT_SET if config.script_path is None else config.script_path
    name = get_vfs_name(config.vfs_path)
    return (
        "[отладка] Параметры запуска:\n"
        f"[отладка]   --vfs:    {vfs}\n"
        f"[отладка]   --script: {script}\n"
        f"[отладка]   имя VFS в приглашении: {name}"
    )


def format_vfs_info(root: Node) -> str:
    """Формирует отладочную строку о размере VFS в памяти."""
    dirs, files = count_nodes(root)
    return f"[отладка] VFS в памяти: каталогов {dirs}, файлов {files}"


def get_identity() -> tuple[str, str]:
    """Возвращает имя пользователя и имя хоста реальной ОС."""
    try:
        username = getpass.getuser()
    except (KeyError, OSError):
        username = DEFAULT_USER
    return username, socket.gethostname()


def make_banner(username: str, hostname: str) -> str:
    """Формирует приветствие со списком доступных команд."""
    commands = ", ".join(COMMANDS)
    return (
        f"Эмулятор запущен под учётной записью {username}@{hostname}\n"
        f"Доступные команды: {commands}\n"
    )


def split_tokens(text: str) -> list[str]:
    """Делит строку на слова по пробелам.

    Слово в двойных или одинарных кавычках может содержать пробелы.
    """
    return [
        next(group for group in match.groups() if group is not None)
        for match in TOKEN_PATTERN.finditer(text)
    ]


def parse_line(line: str) -> tuple[str, list[str]]:
    """Раскрывает переменные окружения и делит строку на слова.

    Возвращает пару (команда, аргументы). Для пустой строки, строки
    комментария и строки, ставшей пустой после раскрытия переменных,
    команда и список аргументов пусты.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(COMMENT_PREFIX):
        return "", []
    tokens = split_tokens(os.path.expandvars(stripped))
    if not tokens:
        return "", []
    return tokens[0], tokens[1:]


def execute(session: Session, line: str) -> Optional[str]:
    """Выполняет одну строку ввода и возвращает текст для вывода.

    Для пустой строки возвращает None. Неизвестная команда и неверные
    аргументы приводят к CommandError, команда exit к ExitRequestedError.
    """
    command, args = parse_line(line)
    if not command:
        return None
    handler = COMMANDS.get(command)
    if handler is None:
        raise CommandError(f"неизвестная команда '{command}'")
    return handler(session, args)


def handle_line(session: Session, line: str, location: str = "") -> bool:
    """Выполняет строку и печатает результат или сообщение об ошибке.

    Параметр location дополняет сообщение об ошибке, например номером
    строки скрипта. Возвращает True, если запрошено завершение работы.
    """
    try:
        output = execute(session, line)
    except CommandError as error:
        print(f"Ошибка{location}: {error}")
    except ExitRequestedError:
        print("Завершение работы эмулятора.")
        return True
    else:
        if output is not None:
            print(output)
    return False


def repl(session: Session) -> None:
    """Цикл чтения и выполнения команд до exit, Ctrl+D или Ctrl+C."""
    while True:
        try:
            line = input(session.prompt())
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if handle_line(session, line):
            return


def read_script(path: str) -> list[str]:
    """Читает стартовый скрипт и возвращает его строки без переводов."""
    try:
        with open(path, encoding=SCRIPT_ENCODING) as script_file:
            return script_file.read().splitlines()
    except UnicodeDecodeError as error:
        raise ScriptError(f"скрипт '{path}' не в кодировке UTF-8") from error
    except OSError as error:
        reason = error.strerror or error
        raise ScriptError(
            f"не удалось прочитать скрипт '{path}': {reason}"
        ) from error


def run_script(session: Session, lines: list[str]) -> bool:
    """Выполняет строки скрипта, имитируя диалог с пользователем.

    Показывает и ввод, и вывод. Ошибочные строки сообщают об ошибке с
    номером строки и пропускаются. Возвращает True, если скрипт
    завершился командой exit.
    """
    for number, line in enumerate(lines, start=1):
        command, _ = parse_line(line)
        if not command:
            continue
        print(f"{session.prompt()}{line.strip()}")
        if handle_line(session, line, f" (строка {number})"):
            return True
    return False


def create_session(
    config: Config, username: str, hostname: str
) -> Session:
    """Загружает VFS (или создаёт пустую) и возвращает сеанс."""
    if config.vfs_path is None:
        root = new_root()
    else:
        root = load_vfs(config.vfs_path)
    return Session(root, get_vfs_name(config.vfs_path), username, hostname)


def report_error(error: Exception, code: int) -> int:
    """Печатает сообщение об ошибке в stderr и возвращает код возврата."""
    print(f"Ошибка: {error}", file=sys.stderr)
    return code


def main(argv: Optional[list[str]] = None) -> int:
    """Точка входа: параметры, VFS, стартовый скрипт, затем REPL."""
    config = parse_args(argv)
    username, hostname = get_identity()
    print(make_banner(username, hostname))
    print(format_config(config))
    try:
        session = create_session(config, username, hostname)
    except VfsError as error:
        return report_error(error, EXIT_VFS_ERROR)
    print(format_vfs_info(session.root))
    print()
    if config.script_path is not None:
        try:
            lines = read_script(config.script_path)
        except ScriptError as error:
            return report_error(error, EXIT_SCRIPT_ERROR)
        if run_script(session, lines):
            return EXIT_OK
    repl(session)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
