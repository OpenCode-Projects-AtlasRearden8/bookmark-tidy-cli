"""Data model: bookmarks and folder trees."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass(eq=False)
class Bookmark:
    title: str
    url: str
    add_date: Optional[int] = None
    icon: Optional[str] = None
    desc: Optional[str] = None
    path: tuple[str, ...] = ()
    order: int = 0
    flags: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.title.strip() or self.url or "(untitled)"

    def path_text(self, sep: str = " > ") -> str:
        return sep.join(self.path) if self.path else "(top level)"


@dataclass(eq=False)
class FolderNode:
    name: str
    parent: Optional["FolderNode"] = field(default=None, repr=False)
    folders: list["FolderNode"] = field(default_factory=list)
    bookmarks: list[Bookmark] = field(default_factory=list)

    def add_folder(self, child: "FolderNode") -> "FolderNode":
        child.parent = self
        self.folders.append(child)
        return child

    def add_bookmark(self, bookmark: Bookmark) -> None:
        self.bookmarks.append(bookmark)

    def folder_path(self) -> tuple[str, ...]:
        parts: list[str] = []
        node: Optional[FolderNode] = self
        while node is not None and node.name:
            parts.append(node.name)
            node = node.parent
        return tuple(reversed(parts))

    def iter_folders(self, include_self: bool = False) -> Iterator["FolderNode"]:
        if include_self:
            yield self
        for child in self.folders:
            yield child
            yield from child.iter_folders()

    def iter_bookmarks(self) -> Iterator[Bookmark]:
        yield from self.bookmarks
        for folder in self.folders:
            yield from folder.iter_bookmarks()

    def counts(self) -> tuple[int, int]:
        folders = sum(1 for _ in self.iter_folders())
        bookmarks = sum(1 for _ in self.iter_bookmarks())
        return folders, bookmarks


def strip_dates(raw: object) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(str(raw), 10)
    except (TypeError, ValueError):
        try:
            return int(str(raw), 16)
        except (TypeError, ValueError):
            return None
