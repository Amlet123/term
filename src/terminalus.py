"""Эмулятор оболочки UNIX-подобной ОС. Этап 2: конфигурация."""

import argparse
import getpass
import os
import socket
import sys
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_VFS_NAME = "vfs"
DEFAULT_USER = "user"
MAX_CD_ARGS = 1
COMMENT_PREFIX = "#"
NOT_SET = "(не задан)"
SCRIPT_ENCODING = "utf-8-sig"
EXIT_OK = 0
EXIT_SCRIPT_ERROR = 1


@dataclass
class Config:
    """Параметры запуска эмулятора, заданные в командной строке."""

    vfs_path: Optional[str] = None
    script_path: Optional[str] = None


class CommandError(Exception):
    """Ошибка выполнения команды, текст которой видит пользователь."""


class ExitRequestedError(Exception):
    """Сигнал о завершении работы эмулятора (команда exit)."""


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
        "--vfs", metavar="ПУТЬ", help="путь к физическому расположению VFS"
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


def get_identity() -> tuple[str, str]:
    """Возвращает имя пользователя и имя хоста реальной ОС."""
    try:
        username = getpass.getuser()
    except (KeyError, OSError):
        username = DEFAULT_USER
    return username, socket.gethostname()


def make_prompt(vfs_name: str, username: str, hostname: str) -> str:
    """Формирует приглашение к вводу, содержащее имя VFS."""
    return f"({vfs_name}) {username}@{hostname}:~$ "


def make_banner(username: str, hostname: str) -> str:
    """Формирует приветствие со списком доступных команд."""
    commands = ", ".join(COMMANDS)
    return (
        f"Эмулятор запущен под учётной записью {username}@{hostname}\n"
        f"Доступные команды: {commands}\n"
    )


def parse_line(line: str) -> tuple[str, list[str]]:
    """Раскрывает переменные окружения и делит строку по пробелам.

    Возвращает пару (команда, аргументы). Для пустой строки, строки
    комментария и строки, ставшей пустой после раскрытия переменных,
    команда и список аргументов пусты.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(COMMENT_PREFIX):
        return "", []
    tokens = os.path.expandvars(stripped).split()
    if not tokens:
        return "", []
    return tokens[0], tokens[1:]


def format_stub(name: str, args: list[str]) -> str:
    """Формирует вывод команды-заглушки: её имя и аргументы."""
    return f"[заглушка] команда: {name}\n[заглушка] аргументы: {args}"


def cmd_ls(args: list[str]) -> str:
    """Заглушка команды ls."""
    return format_stub("ls", args)


def cmd_cd(args: list[str]) -> str:
    """Заглушка команды cd. Принимает не более одного аргумента."""
    if len(args) > MAX_CD_ARGS:
        raise CommandError("cd: слишком много аргументов")
    return format_stub("cd", args)


def cmd_exit(args: list[str]) -> str:
    """Команда exit. Аргументы не допускаются."""
    if args:
        raise CommandError("exit: команда не принимает аргументов")
    raise ExitRequestedError()


COMMANDS: dict[str, Callable[[list[str]], str]] = {
    "ls": cmd_ls,
    "cd": cmd_cd,
    "exit": cmd_exit,
}


def execute(line: str) -> Optional[str]:
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
    return handler(args)


def handle_line(line: str, location: str = "") -> bool:
    """Выполняет строку и печатает результат или сообщение об ошибке.

    Параметр location дополняет сообщение об ошибке, например номером
    строки скрипта. Возвращает True, если запрошено завершение работы.
    """
    try:
        output = execute(line)
    except CommandError as error:
        print(f"Ошибка{location}: {error}")
    except ExitRequestedError:
        print("Завершение работы эмулятора.")
        return True
    else:
        if output is not None:
            print(output)
    return False


def repl(prompt: str) -> None:
    """Цикл чтения и выполнения команд до exit, Ctrl+D или Ctrl+C."""
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if handle_line(line):
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


def run_script(lines: list[str], prompt: str) -> bool:
    """Выполняет строки скрипта, имитируя диалог с пользователем.

    Показывает и ввод, и вывод. Ошибочные строки сообщают об ошибке с
    номером строки и пропускаются. Возвращает True, если скрипт
    завершился командой exit.
    """
    for number, line in enumerate(lines, start=1):
        command, _ = parse_line(line)
        if not command:
            continue
        print(f"{prompt}{line.strip()}")
        if handle_line(line, f" (строка {number})"):
            return True
    return False


def main(argv: Optional[list[str]] = None) -> int:
    """Точка входа: параметры, отладочный вывод, скрипт, затем REPL."""
    config = parse_args(argv)
    username, hostname = get_identity()
    print(make_banner(username, hostname))
    print(format_config(config))
    print()
    prompt = make_prompt(get_vfs_name(config.vfs_path), username, hostname)
    if config.script_path is not None:
        try:
            lines = read_script(config.script_path)
        except ScriptError as error:
            print(f"Ошибка: {error}", file=sys.stderr)
            return EXIT_SCRIPT_ERROR
        if run_script(lines, prompt):
            return EXIT_OK
    repl(prompt)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
