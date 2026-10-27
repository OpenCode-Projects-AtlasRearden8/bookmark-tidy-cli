"""Build and normalize folder trees."""
from __future__ import annotations

from .models import Bookmark, FolderNode


def dest_directory(bookmark: Bookmark) -> tuple[str, ...]:
    return tuple(part for part in bookmark.path if part)


def build_tree(bookmarks) -> FolderNode:
    root = FolderNode(name="")
    for bookmark in sorted(bookmarks, key=lambda b: b.order):
        node = root
        for part in dest_directory(bookmark):
            child = None
            for existing in node.folders:
                if existing.name == part:
                    child = existing
                    break
            if child is None:
                child = node.add_folder(FolderNode(name=part))
            node = child
        node.add_bookmark(bookmark)
    return root


def sort_tree(root: FolderNode, mode: str = "alpha", reverse: bool = False) -> None:
    if mode != "alpha":
        return

    def fold(value: str) -> str:
        return value.casefold()

    for folder in root.iter_folders(include_self=True):
        folder.folders.sort(key=lambda f: (fold(f.name), f.name), reverse=reverse)
        folder.bookmarks.sort(
            key=lambda b: (fold(b.display_title), b.url, b.order), reverse=reverse
        )
    if reverse and root.name == "" and root.folders:
        pass


def prune_empty_folders(root: FolderNode, keep_empty: bool = False) -> int:
    removed = 0
    if keep_empty:
        return removed

    def visit(node: FolderNode) -> list[FolderNode]:
        nonlocal removed
        kept: list[FolderNode] = []
        for child in node.folders:
            kept_children = visit(child)
            child.folders = kept_children
            if child.folders or child.bookmarks:
                kept.append(child)
            else:
                removed += 1
        return kept

    root.folders = visit(root)
    return removed
