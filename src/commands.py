"""Состояние сеанса эмулятора и команды оболочки."""

from dataclasses import dataclass
from typing import Callable, Optional

from vfs import Node, VfsError, save_vfs

MAX_CD_ARGS = 1
SAVE_ARGS = 1
PROMPT_LOCATION = "~"


class CommandError(Exception):
    """Ошибка выполнения команды, текст которой видит пользователь."""


class ExitRequestedError(Exception):
    """Сигнал о завершении работы эмулятора (команда exit)."""


@dataclass
class Session:
    """Состояние сеанса: VFS в памяти и данные для приглашения к вводу."""

    root: Node
    vfs_name: str
    username: str
    hostname: str

    def prompt(self) -> str:
        """Формирует приглашение к вводу, содержащее имя VFS."""
        identity = f"{self.username}@{self.hostname}"
        return f"({self.vfs_name}) {identity}:{PROMPT_LOCATION}$ "


def format_stub(name: str, args: list[str]) -> str:
    """Формирует вывод команды-заглушки: её имя и аргументы."""
    return f"[заглушка] команда: {name}\n[заглушка] аргументы: {args}"


def cmd_ls(session: Session, args: list[str]) -> Optional[str]:
    """Заглушка команды ls."""
    return format_stub("ls", args)


def cmd_cd(session: Session, args: list[str]) -> Optional[str]:
    """Заглушка команды cd. Принимает не более одного аргумента."""
    if len(args) > MAX_CD_ARGS:
        raise CommandError("cd: слишком много аргументов")
    return format_stub("cd", args)


def cmd_exit(session: Session, args: list[str]) -> Optional[str]:
    """Команда exit. Аргументы не допускаются."""
    if args:
        raise CommandError("exit: команда не принимает аргументов")
    raise ExitRequestedError()


def cmd_vfs_save(session: Session, args: list[str]) -> Optional[str]:
    """Команда vfs-save ПУТЬ: сохраняет VFS из памяти в XML-файл."""
    if len(args) != SAVE_ARGS:
        raise CommandError("vfs-save: требуется один аргумент: путь к файлу")
    path = args[0]
    try:
        save_vfs(session.root, path)
    except VfsError as error:
        raise CommandError(f"vfs-save: {error}") from error
    return f"VFS сохранена: {path}"


COMMANDS: dict[str, Callable[[Session, list[str]], Optional[str]]] = {
    "ls": cmd_ls,
    "cd": cmd_cd,
    "exit": cmd_exit,
    "vfs-save": cmd_vfs_save,
}
