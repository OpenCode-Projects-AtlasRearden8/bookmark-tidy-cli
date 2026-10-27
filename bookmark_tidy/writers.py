"""Writers: import-ready HTML, LLM-friendly Markdown, and JSON report."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .analysis import FLAG_LABELS
from .models import Bookmark, FolderNode

_HEADER_LINES = [
    "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
    "<!-- This is an automatically generated file.",
    "     Made by bookmark-tidy. You can import it in Chrome, Firefox, or Edge.",
    "     Your browser's own bookmarks were NOT changed; import on purpose. -->",
    '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
    "<TITLE>Bookmarks</TITLE>",
    "<H1>Bookmarks</H1>",
]

_INDENT = "    "


def _escape(value: str) -> str:
    from html import escape

    return escape(value or "", quote=True)


def bookmark_line(bookmark: Bookmark, indent: int) -> str:
    pad = _INDENT * indent
    attrs = ""
    if bookmark.add_date is not None:
        attrs += f' ADD_DATE="{int(bookmark.add_date)}"'
    if bookmark.icon:
        attrs += f' ICON="{_escape(bookmark.icon)}"'
    title = _escape(bookmark.display_title)
    href = _escape(bookmark.url)
    return f"{pad}<DT><A HREF=\"{href}\"{attrs}>{title}</A>"


def folder_lines(folder: FolderNode, indent: int, out: list[str]) -> None:
    pad = _INDENT * indent
    out.append(f"{pad}<DT><H3>{_escape(folder.name)}</H3>")
    out.append(f"{pad}<DL><p>")
    child_pad = _INDENT * (indent + 1)
    for child in folder.folders:
        folder_lines(child, indent + 1, out)
    for bookmark in folder.bookmarks:
        out.append(bookmark_line(bookmark, indent + 1))
        if bookmark.desc:
            out.append(f"{child_pad}<DD>{_escape(bookmark.desc)}")
    out.append(f"{pad}</DL><p>")


def bookmarks_html(root: FolderNode) -> str:
    lines = list(_HEADER_LINES)
    lines.append("<DL><p>")
    for child in root.folders:
        folder_lines(child, 1, lines)
    for bookmark in root.bookmarks:
        lines.append(bookmark_line(bookmark, 1))
        if bookmark.desc:
            lines.append(f"{_INDENT}<DD>{_escape(bookmark.desc)}")
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"


def _md_escape(value: str) -> str:
    text = (value or "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    text = text.replace("`", "'")
    text = " ".join(text.split())
    return text


def _md_link(bookmark: Bookmark) -> str:
    title = _md_escape(bookmark.display_title)
    if bookmark.url.startswith(("http://", "https://")):
        return f"[{title}](<{bookmark.url}>)"
    if bookmark.url:
        return f"{title} (`{bookmark.url}`)"
    return f"{title} `(no URL)`"


def _md_flags(bookmark: Bookmark) -> str:
    if not bookmark.flags:
        return ""
    labels = [f"{flag}" for flag in bookmark.flags]
    return f" *(flag: {', '.join(labels)})*"


def bookmarks_markdown(root: FolderNode, generated_at: str | None = None) -> str:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    folders, link_count = root.counts()
    lines = [
        "# Bookmarks",
        "",
        f"Tidied by bookmark-tidy on {generated_at}. {link_count} links in {folders} folders.",
        "",
        "This is a plain index you can paste into any LLM chat, notes app, or README.",
        "",
    ]

    def emit(folder: FolderNode, depth: int) -> None:
        if depth == 0:
            lines.append(f"## {_md_escape(folder.name)}")
            lines.append("")
        else:
            pad = "  " * depth
            lines.append(f"{pad}- **{_md_escape(folder.name)}**")
        bookmark_pad = "  " * (depth + 1 if depth > 0 else 0)
        if folder.bookmarks and depth > 0:
            pass
        for bookmark in folder.bookmarks:
            lines.append(f"{bookmark_pad}- {_md_link(bookmark)}{_md_flags(bookmark)}")
        for child in folder.folders:
            emit(child, depth + 1)

    for child in root.folders:
        emit(child, 0)
    if root.bookmarks:
        lines.append("## Loose links")
        lines.append("")
        for bookmark in root.bookmarks:
            lines.append(f"- {_md_link(bookmark)}{_md_flags(bookmark)}")
        lines.append("")
    elif lines[-1] != "":
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_json_report(report: dict, path: Path) -> None:
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
