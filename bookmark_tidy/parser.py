"""Netscape-format bookmark HTML parser (Chrome / Firefox / Edge exports)."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from .models import Bookmark, FolderNode, strip_dates

_OWNED_ATTRS = {"href", "add_date", "icon"}


class _NetscapeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = FolderNode(name="")
        self.stack: list[FolderNode] = [self.root]
        self._buf: list[str] = []
        self._target: str | None = None
        self._pending: dict | None = None
        self._pending_folder: FolderNode | None = None
        self._auto_closed = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._target == "dd" and tag in ("a", "h3", "dd"):
            self._flush_dd()
        raw = {}
        for k, v in attrs:
            raw[k.lower()] = v if v is not None else ""
        if tag == "a":
            if self._pending is not None:
                self._auto_closed += 1
                self._close_bookmark()
            self._pending = {
                "url": raw.get("href", "").strip(),
                "add_date": strip_dates(raw.get("add_date")),
                "icon": raw.get("icon") or None,
            }
            self._buf = []
            self._target = "a"
        elif tag == "h3":
            self._pending_folder = None
            self._buf = []
            self._target = "h3"
        elif tag == "dl":
            node = self._pending_folder if self._pending_folder is not None else self.stack[-1]
            self._pending_folder = None
            self.stack.append(node)
        elif tag == "dd":
            self._flush_dd()
            self._buf = []
            self._target = "dd"

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a":
            self._close_bookmark()
        elif tag == "h3":
            name = " ".join("".join(self._buf).split())
            self._target = None
            if name:
                parent = self.stack[-1]
                self._pending_folder = parent.add_folder(FolderNode(name=name, parent=parent))
        elif tag == "dl":
            self._flush_dd()
            if len(self.stack) > 1:
                self.stack.pop()
        elif tag == "dd":
            self._flush_dd()

    def _flush_dd(self) -> None:
        if self._target != "dd":
            return
        text = " ".join("".join(self._buf).split())
        self._target = None
        self._buf = []
        if text:
            items = self.stack[-1].bookmarks
            if items and items[-1].desc is None:
                items[-1].desc = text

    def handle_data(self, data):
        if self._target is not None:
            self._buf.append(data)

    def _close_bookmark(self):
        if self._pending is None:
            return
        title = " ".join("".join(self._buf).split()) if self._target == "a" else ""
        self._pending = self._pending or {}
        url = self._pending.get("url", "")
        folder = self.stack[-1]
        bookmark = Bookmark(
            title=title,
            url=url,
            add_date=self._pending.get("add_date"),
            icon=self._pending.get("icon"),
            path=folder.folder_path(),
        )
        folder.add_bookmark(bookmark)
        self._pending = None
        self._target = None


def parse_html(text: str) -> tuple[FolderNode, list[str]]:
    parser = _NetscapeParser()
    notes: list[str] = []
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:  # extremely defensive; html.parser rarely raises
        notes.append(f"parser warning: {exc}")
    if parser._target == "dd":
        parser._flush_dd()
    if parser._pending is not None:
        parser._auto_closed += 1
        parser._close_bookmark()
    if parser._auto_closed:
        notes.append(f"{parser._auto_closed} anchor tag(s) were unclosed and were auto-closed")
    return parser.root, notes


def read_text(path) -> tuple[str, str]:
    data = Path(path).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
        return data.decode("utf-8", errors="replace"), "utf-8 (BOM)"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1 (fallback)"
