"""Виртуальная файловая система в памяти и её XML-формат."""

import base64
import binascii
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree

SEPARATOR = "/"
CURRENT_DIR = "."
PARENT_DIR = ".."
ROOT_TAG = "vfs"
DIR_TAG = "dir"
FILE_TAG = "file"
NAME_ATTR = "name"
ENCODING_ATTR = "encoding"
TEXT = "text"
BASE64 = "base64"
XML_ENCODING = "utf-8"


class VfsError(Exception):
    """Ошибка работы с виртуальной файловой системой."""


@dataclass(eq=False)
class Node:
    """Узел VFS: каталог с дочерними узлами или файл с содержимым."""

    name: str
    is_dir: bool
    children: dict = field(default_factory=dict)
    content: bytes = b""
    encoding: str = TEXT
    parent: Optional["Node"] = field(default=None, repr=False)


def new_root() -> Node:
    """Создаёт пустую VFS: один корневой каталог."""
    return Node(name="", is_dir=True)


def add_child(parent: Node, child: Node) -> None:
    """Добавляет узел в каталог, проверяя имя и отсутствие дубликата."""
    name = child.name
    if not name or SEPARATOR in name or name in (CURRENT_DIR, PARENT_DIR):
        raise VfsError(f"недопустимое имя в VFS: '{name}'")
    if name in parent.children:
        raise VfsError(f"повторяющееся имя в VFS: '{name}'")
    child.parent = parent
    parent.children[name] = child


def add_dir(parent: Node, name: str) -> Node:
    """Создаёт каталог внутри parent и возвращает его."""
    node = Node(name=name, is_dir=True)
    add_child(parent, node)
    return node


def add_file(
    parent: Node, name: str, content: bytes = b"", encoding: str = TEXT
) -> Node:
    """Создаёт файл внутри parent и возвращает его."""
    node = Node(name=name, is_dir=False, content=content, encoding=encoding)
    add_child(parent, node)
    return node


def node_path(node: Node) -> str:
    """Возвращает абсолютный путь узла, например /home/user."""
    parts = []
    while node.parent is not None:
        parts.append(node.name)
        node = node.parent
    return SEPARATOR + SEPARATOR.join(reversed(parts))


def resolve(root: Node, cwd: Node, path: str) -> Node:
    """Находит узел по абсолютному или относительному пути."""
    node = root if path.startswith(SEPARATOR) else cwd
    for part in path.split(SEPARATOR):
        if not part or part == CURRENT_DIR:
            continue
        if part == PARENT_DIR:
            node = node.parent or node
            continue
        if not node.is_dir:
            raise VfsError(f"{path}: не каталог")
        if part not in node.children:
            raise VfsError(f"{path}: нет такого файла или каталога")
        node = node.children[part]
    return node


def count_nodes(root: Node) -> tuple[int, int]:
    """Возвращает число каталогов (без корня) и число файлов в VFS."""
    dirs = files = 0
    stack = list(root.children.values())
    while stack:
        node = stack.pop()
        if node.is_dir:
            dirs += 1
            stack.extend(node.children.values())
        else:
            files += 1
    return dirs, files


def decode_base64(name: str, text: str) -> bytes:
    """Декодирует base64, допуская пробелы и переводы строк."""
    try:
        return base64.b64decode("".join(text.split()), validate=True)
    except binascii.Error as error:
        raise VfsError(f"файл '{name}': некорректные данные base64") from error


def read_content(name: str, element: ElementTree.Element) -> tuple[bytes, str]:
    """Возвращает содержимое файла из XML-элемента и его кодировку."""
    encoding = element.get(ENCODING_ATTR, TEXT)
    text = element.text or ""
    if encoding == TEXT:
        return text.encode(XML_ENCODING), encoding
    if encoding == BASE64:
        return decode_base64(name, text), encoding
    raise VfsError(f"файл '{name}': неизвестная кодировка '{encoding}'")


def fill_directory(directory: Node, element: ElementTree.Element) -> None:
    """Рекурсивно заполняет каталог по дочерним элементам XML."""
    for child in element:
        if child.tag not in (DIR_TAG, FILE_TAG):
            raise VfsError(f"неизвестный элемент <{child.tag}>")
        name = child.get(NAME_ATTR)
        if name is None:
            raise VfsError(f"элемент <{child.tag}> без атрибута {NAME_ATTR}")
        if child.tag == DIR_TAG:
            fill_directory(add_dir(directory, name), child)
        else:
            content, encoding = read_content(name, child)
            add_file(directory, name, content, encoding)


def load_vfs(path: str) -> Node:
    """Загружает VFS из XML-файла в память и возвращает корень."""
    try:
        document = ElementTree.parse(path)
    except ElementTree.ParseError as error:
        raise VfsError(
            f"'{path}' не является корректным XML: {error}"
        ) from error
    except OSError as error:
        reason = error.strerror or error
        raise VfsError(
            f"не удалось прочитать VFS '{path}': {reason}"
        ) from error
    element = document.getroot()
    if element.tag != ROOT_TAG:
        raise VfsError(f"корневой элемент должен быть <{ROOT_TAG}>")
    root = new_root()
    fill_directory(root, element)
    return root


def encode_content(node: Node) -> str:
    """Преобразует содержимое файла в текст для XML по его кодировке."""
    if node.encoding == BASE64:
        return base64.b64encode(node.content).decode("ascii")
    return node.content.decode(XML_ENCODING)


def fill_element(element: ElementTree.Element, directory: Node) -> None:
    """Рекурсивно переносит содержимое каталога в XML-элемент."""
    for node in directory.children.values():
        if node.is_dir:
            child = ElementTree.SubElement(
                element, DIR_TAG, {NAME_ATTR: node.name}
            )
            fill_element(child, node)
        else:
            attributes = {NAME_ATTR: node.name, ENCODING_ATTR: node.encoding}
            child = ElementTree.SubElement(element, FILE_TAG, attributes)
            child.text = encode_content(node)


def save_vfs(root: Node, path: str) -> None:
    """Сохраняет VFS из памяти в XML-файл в исходном формате."""
    element = ElementTree.Element(ROOT_TAG)
    fill_element(element, root)
    ElementTree.indent(element)
    try:
        ElementTree.ElementTree(element).write(
            path, encoding=XML_ENCODING, xml_declaration=True
        )
    except OSError as error:
        reason = error.strerror or error
        raise VfsError(
            f"не удалось сохранить VFS '{path}': {reason}"
        ) from error
