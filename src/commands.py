"""Состояние сеанса эмулятора и команды оболочки."""

import fnmatch
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from vfs import (
    CURRENT_DIR,
    PARENT_DIR,
    SEPARATOR,
    Node,
    VfsError,
    node_path,
    resolve,
    remove_empty_dir,
    save_vfs,
)

MAX_CD_ARGS = 1
MAX_HISTORY_ARGS = 1
SAVE_ARGS = 1
SINGLE_PATH = 1
OPTION_PREFIX = "-"
LONG_FLAG = "-l"
CLEAR_FLAG = "-c"
NAME_FLAG = "-name"
TYPE_FLAG = "-type"
PARENTS_FLAG = "-p"
VERBOSE_FLAG = "-v"
TYPE_FILE = "f"
TYPE_DIR = "d"
KIND_DIR = "d"
KIND_FILE = "-"
NO_SIZE = "-"
CLEAR_SEQUENCE = "\033[2J\033[H"
HISTORY_WIDTH = 5


class CommandError(Exception):
    """Ошибка выполнения команды, текст которой видит пользователь."""


class ExitRequestedError(Exception):
    """Сигнал о завершении работы эмулятора (команда exit)."""


@dataclass
class Session:
    """Состояние сеанса: VFS, текущий каталог, история и приглашение."""

    root: Node
    vfs_name: str
    username: str
    hostname: str
    cwd: Node = field(init=False)
    history: list = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Делает текущим каталогом корень VFS."""
        self.cwd = self.root

    def prompt(self) -> str:
        """Формирует приглашение к вводу: имя VFS и текущий каталог."""
        identity = f"{self.username}@{self.hostname}"
        return f"({self.vfs_name}) {identity}:{node_path(self.cwd)}$ "


@dataclass
class FindOptions:
    """Разобранные параметры команды find."""

    path: str = CURRENT_DIR
    pattern: Optional[str] = None
    kind: Optional[str] = None


@dataclass
class RmdirOptions:
    """Разобранные параметры команды rmdir."""

    parents: bool = False
    verbose: bool = False
    paths: list = field(default_factory=list)


def lookup(session: Session, command: str, path: str) -> Node:
    """Находит узел по пути, превращая ошибку VFS в ошибку команды."""
    try:
        return resolve(session.root, session.cwd, path)
    except VfsError as error:
        raise CommandError(f"{command}: {error}") from error


def is_option(arg: str) -> bool:
    """Проверяет, что аргумент выглядит как параметр, например -l."""
    return arg.startswith(OPTION_PREFIX) and arg != OPTION_PREFIX


def split_ls_args(args: list[str]) -> tuple[bool, list[str]]:
    """Отделяет флаг -l от путей. Другие параметры недопустимы."""
    long_format = False
    paths = []
    for arg in args:
        if arg == LONG_FLAG:
            long_format = True
        elif is_option(arg):
            raise CommandError(f"ls: неизвестный параметр '{arg}'")
        else:
            paths.append(arg)
    return long_format, paths


def format_entry(node: Node, label: str, long_format: bool) -> str:
    """Формирует строку ls: имя, а с -l ещё тип и размер в байтах."""
    if not long_format:
        return label
    kind = KIND_DIR if node.is_dir else KIND_FILE
    size = NO_SIZE if node.is_dir else str(len(node.content))
    return f"{kind} {size:>8} {label}"


def list_node(node: Node, path: str, long_format: bool) -> list[str]:
    """Возвращает строки ls для каталога или для одного файла."""
    if not node.is_dir:
        return [format_entry(node, path, long_format)]
    return [
        format_entry(node.children[name], name, long_format)
        for name in sorted(node.children)
    ]


def cmd_ls(session: Session, args: list[str]) -> Optional[str]:
    """Команда ls [-l] [ПУТЬ...]: показывает содержимое каталогов."""
    long_format, paths = split_ls_args(args)
    targets = paths or [CURRENT_DIR]
    nodes = [lookup(session, "ls", path) for path in targets]
    blocks = []
    for path, node in zip(targets, nodes):
        lines = list_node(node, path, long_format)
        if len(targets) > SINGLE_PATH:
            lines.insert(0, f"{path}:")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or None


def cmd_cd(session: Session, args: list[str]) -> Optional[str]:
    """Команда cd [ПУТЬ]: меняет текущий каталог, без пути идёт в корень."""
    if len(args) > MAX_CD_ARGS:
        raise CommandError("cd: слишком много аргументов")
    target = args[0] if args else SEPARATOR
    node = lookup(session, "cd", target)
    if not node.is_dir:
        raise CommandError(f"cd: {target}: не каталог")
    session.cwd = node
    return None


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


def cmd_clear(session: Session, args: list[str]) -> Optional[str]:
    """Команда clear: очищает экран терминала."""
    if args:
        raise CommandError("clear: команда не принимает аргументов")
    print(CLEAR_SEQUENCE, end="")
    return None


def parse_count(text: str) -> int:
    """Преобразует аргумент history в неотрицательное число."""
    if not text.isdecimal():
        raise CommandError(f"history: {text}: нужно неотрицательное число")
    return int(text)


def cmd_history(session: Session, args: list[str]) -> Optional[str]:
    """Команда history [N | -c]: показывает или очищает историю команд."""
    if args == [CLEAR_FLAG]:
        session.history.clear()
        return None
    if len(args) > MAX_HISTORY_ARGS:
        raise CommandError("history: слишком много аргументов")
    entries = list(enumerate(session.history, start=1))
    if args:
        entries = entries[max(len(entries) - parse_count(args[0]), 0):]
    lines = [f"{number:>{HISTORY_WIDTH}}  {line}" for number, line in entries]
    return "\n".join(lines) or None


def read_flag_value(flag: str, arguments: Iterator[str]) -> str:
    """Берёт значение параметра find из оставшихся аргументов."""
    value = next(arguments, None)
    if value is None:
        raise CommandError(f"find: для {flag} требуется значение")
    return value


def check_type(value: str) -> str:
    """Проверяет значение параметра -type: f (файл) или d (каталог)."""
    if value not in (TYPE_FILE, TYPE_DIR):
        raise CommandError(f"find: неверный тип '{value}', нужен f или d")
    return value


def parse_find_args(args: list[str]) -> FindOptions:
    """Разбирает аргументы find: путь, -name ШАБЛОН, -type f|d."""
    options = FindOptions()
    path_given = False
    arguments = iter(args)
    for arg in arguments:
        if arg == NAME_FLAG:
            options.pattern = read_flag_value(arg, arguments)
        elif arg == TYPE_FLAG:
            options.kind = check_type(read_flag_value(arg, arguments))
        elif is_option(arg):
            raise CommandError(f"find: неизвестный параметр '{arg}'")
        elif path_given:
            raise CommandError("find: допускается только один путь")
        else:
            options.path = arg
            path_given = True
    return options


def matches(node: Node, options: FindOptions) -> bool:
    """Проверяет, подходит ли узел под условия -name и -type."""
    kind_ok = options.kind is None or (options.kind == TYPE_DIR) == node.is_dir
    name_ok = options.pattern is None or fnmatch.fnmatchcase(
        node.name, options.pattern
    )
    return kind_ok and name_ok


def walk(node: Node, label: str) -> Iterator[tuple[str, Node]]:
    """Обходит узел и его потомков по алфавиту, отдавая пары (путь, узел)."""
    yield label, node
    if node.is_dir:
        prefix = label.rstrip(SEPARATOR)
        for name in sorted(node.children):
            yield from walk(node.children[name], f"{prefix}{SEPARATOR}{name}")


def cmd_find(session: Session, args: list[str]) -> Optional[str]:
    """Команда find [ПУТЬ] [-name ШАБЛОН] [-type f|d]: ищет узлы VFS."""
    options = parse_find_args(args)
    label = options.path or CURRENT_DIR
    start = lookup(session, "find", label)
    lines = [
        path for path, node in walk(start, label) if matches(node, options)
    ]
    return "\n".join(lines) or None


def parse_rmdir_args(args: list[str]) -> RmdirOptions:
    """Разбирает аргументы rmdir: флаги -p, -v и один или несколько путей."""
    options = RmdirOptions()
    for arg in args:
        if arg == PARENTS_FLAG:
            options.parents = True
        elif arg == VERBOSE_FLAG:
            options.verbose = True
        elif is_option(arg):
            raise CommandError(f"rmdir: неизвестный параметр '{arg}'")
        else:
            options.paths.append(arg)
    if not options.paths:
        raise CommandError("rmdir: не указан каталог")
    return options


def parent_chain(path: str) -> list[str]:
    """Возвращает путь и пути его родителей: a/b/c даёт a/b/c, a/b, a."""
    chain = []
    current = path.rstrip(SEPARATOR)
    while current and current not in (CURRENT_DIR, PARENT_DIR):
        chain.append(current)
        head, separator, _ = current.rpartition(SEPARATOR)
        if not separator:
            break
        current = head.rstrip(SEPARATOR)
    return chain or [path]


def remove_directory(session: Session, path: str) -> None:
    """Удаляет один пустой каталог, не позволяя удалить текущий."""
    node = lookup(session, "rmdir", path)
    if node is session.cwd and node.parent is not None:
        raise CommandError(f"rmdir: {path}: нельзя удалить текущий каталог")
    try:
        remove_empty_dir(node)
    except VfsError as error:
        raise CommandError(f"rmdir: {path}: {error}") from error


def cmd_rmdir(session: Session, args: list[str]) -> Optional[str]:
    """Команда rmdir [-p] [-v] ПУТЬ...: удаляет пустые каталоги из VFS."""
    options = parse_rmdir_args(args)
    for path in options.paths:
        targets = parent_chain(path) if options.parents else [path]
        for target in targets:
            remove_directory(session, target)
            if options.verbose:
                print(f"rmdir: удалён каталог '{target}'")
    return None


COMMANDS: dict[str, Callable[[Session, list[str]], Optional[str]]] = {
    "ls": cmd_ls,
    "cd": cmd_cd,
    "exit": cmd_exit,
    "vfs-save": cmd_vfs_save,
    "clear": cmd_clear,
    "history": cmd_history,
    "find": cmd_find,
    "rmdir": cmd_rmdir,
}
