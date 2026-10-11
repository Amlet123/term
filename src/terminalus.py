"""Эмулятор оболочки UNIX-подобной ОС. Этап 1: REPL."""

import getpass
import os
import socket
from typing import Callable, Optional

VFS_NAME = "vfs"
DEFAULT_USER = "user"
MAX_CD_ARGS = 1


class CommandError(Exception):
    """Ошибка выполнения команды, текст которой видит пользователь."""


class ExitRequested(Exception):
    """Сигнал о завершении работы эмулятора (команда exit)."""


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

    Возвращает пару (команда, аргументы). Если после раскрытия
    переменных ничего не осталось, команда и список аргументов пусты.
    """
    tokens = os.path.expandvars(line).split()
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
    raise ExitRequested()


COMMANDS: dict[str, Callable[[list[str]], str]] = {
    "ls": cmd_ls,
    "cd": cmd_cd,
    "exit": cmd_exit,
}


def execute(line: str) -> Optional[str]:
    """Выполняет одну строку ввода и возвращает текст для вывода.

    Для пустой строки возвращает None. Неизвестная команда и неверные
    аргументы приводят к CommandError, команда exit к ExitRequested.
    """
    command, args = parse_line(line)
    if not command:
        return None
    handler = COMMANDS.get(command)
    if handler is None:
        raise CommandError(f"неизвестная команда '{command}'")
    return handler(args)


def repl(prompt: str) -> None:
    """Цикл чтения и выполнения команд до exit, Ctrl+D или Ctrl+C."""
    while True:
        try:
            output = execute(input(prompt))
        except CommandError as error:
            print(f"Ошибка: {error}")
        except ExitRequested:
            print("Завершение работы эмулятора.")
            return
        except (EOFError, KeyboardInterrupt):
            print()
            return
        else:
            if output is not None:
                print(output)


def main() -> None:
    """Точка входа: собирает приглашение и запускает REPL."""
    username, hostname = get_identity()
    print(make_banner(username, hostname))
    repl(make_prompt(VFS_NAME, username, hostname))


if __name__ == "__main__":
    main()
