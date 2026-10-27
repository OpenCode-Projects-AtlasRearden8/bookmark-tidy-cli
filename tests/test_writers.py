import json

from bookmark_tidy.parser import parse_html
from bookmark_tidy.treeops import build_tree, prune_empty_folders, sort_tree
from bookmark_tidy.writers import (
    bookmarks_html,
    bookmarks_markdown,
    write_json_report,
)

from .conftest import FIXTURES


def load(name):
    return parse_html((FIXTURES / name).read_text(encoding="utf-8"))


def test_html_round_trip_preserves_everything():
    root, _ = load("sample_chrome.html")
    tree = build_tree(list(root.iter_bookmarks()))
    html = bookmarks_html(tree)
    again, notes = parse_html(html)
    folders, bookmarks = again.counts()
    assert (folders, bookmarks) == (3, 12)
    assert notes == []


def test_html_round_trip_survives_messy_titles():
    root, _ = load("messy.html")
    tree = build_tree(list(root.iter_bookmarks()))
    prune_empty_folders(tree)
    again, _ = parse_html(bookmarks_html(tree))
    titles = {b.title for b in again.iter_bookmarks()}
    assert 'A & B "quoted"' in titles


def test_html_starts_with_netscape_header():
    root, _ = load("sample_firefox.html")
    html = bookmarks_html(build_tree(list(root.iter_bookmarks())))
    assert html.startswith('<!DOCTYPE NETSCAPE-Bookmark-file-1>')
    assert "<DL><p>" in html
    assert "</DL><p>" in html


def test_markdown_index_shape():
    root, _ = load("sample_chrome.html")
    tree = build_tree(list(root.iter_bookmarks()))
    sort_tree(tree)
    prune_empty_folders(tree)
    md = bookmarks_markdown(tree, generated_at="2026-01-01 00:00 UTC")
    assert md.startswith("# Bookmarks")
    assert "## Bookmarks bar" in md
    assert "- **Python**" in md
    assert "[Python Home](<https://www.python.org/>)" in md
    assert "12 links in 3 folders" in md
    assert "any LLM chat" in md


def test_markdown_escapes_and_flags():
    from bookmark_tidy.models import Bookmark, FolderNode

    tree = FolderNode(name="")
    folder = tree.add_folder(FolderNode(name="Reading [list]"))
    weird = Bookmark(title="Test [brackets]", url="https://x.example/a_(b)?q=1")
    weird.flags = ["local-file"]
    folder.add_bookmark(weird)
    local = Bookmark(title="Local Only", url="file:///C:/notes.txt")
    local.flags = ["local-file"]
    folder.add_bookmark(local)
    md = bookmarks_markdown(tree)
    assert "## Reading \\[list\\]" in md
    assert "- [Test \\[brackets\\]](<https://x.example/a_(b)?q=1>) *(flag: local-file)*" in md
    assert "Local Only (`file:///C:/notes.txt`) *(flag: local-file)*" in md


def test_markdown_loose_links_section():
    from bookmark_tidy.models import Bookmark, FolderNode

    tree = FolderNode(name="")
    tree.add_bookmark(Bookmark(title="Loose", url="https://loose.example/"))
    md = bookmarks_markdown(tree)
    assert "## Loose links" in md
    assert "- [Loose](<https://loose.example/>)" in md


def test_json_report_roundtrip(tmp_path):
    from bookmark_tidy.writers import write_json_report

    payload = {"tool": "bookmark-tidy 1.0.0", "ok": True, "note": "caf\u00e9"}
    path = tmp_path / "report.json"
    write_json_report(payload, path)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
