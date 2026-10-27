from bookmark_tidy.parser import parse_html
from bookmark_tidy.treeops import (
    build_tree,
    dest_directory,
    prune_empty_folders,
    sort_tree,
)

from .conftest import FIXTURES


def load_parsed(name):
    root, _ = parse_html((FIXTURES / name).read_text(encoding="utf-8"))
    return root


def load_bookmarks(name):
    return list(load_parsed(name).iter_bookmarks())


def test_dest_directory_follows_source_folders():
    root = load_parsed("sample_chrome.html")
    doc = next(b for b in root.iter_bookmarks() if b.title == "Python Docs")
    assert doc.path == ("Bookmarks bar", "Python")
    assert dest_directory(doc) == ("Bookmarks bar", "Python")


def test_build_tree_merges_paths():
    tree = build_tree(load_bookmarks("sample_chrome.html"))
    top = [f.name for f in tree.folders]
    assert top == ["Bookmarks bar", "Other bookmarks"]
    bar = tree.folders[0]
    assert [f.name for f in bar.folders] == ["Python"]
    python = bar.folders[0]
    assert python.folders == []
    assert [b.title for b in python.bookmarks] == [
        "Python Docs",
        "Real Python",
        "Real Python Tutorials",
        "Example Site",
        "Example site",
    ]
    bar_titles = [b.title for b in bar.bookmarks]
    assert "Python Home" in bar_titles


def test_sort_tree_alpha_folders_then_links():
    tree = build_tree(load_bookmarks("sample_chrome.html"))
    sort_tree(tree)
    top = [f.name for f in tree.folders]
    assert top == sorted(top, key=lambda s: (s.casefold(), s))
    bar = next(f for f in tree.folders if f.name == "Bookmarks bar")
    titles = [b.display_title for b in bar.bookmarks]
    assert titles == sorted(titles, key=lambda s: (s.casefold(), s))


def test_sort_tree_reverse():
    tree = build_tree(load_bookmarks("sample_chrome.html"))
    sort_tree(tree, reverse=True)
    bar = next(f for f in tree.folders if f.name == "Bookmarks bar")
    titles = [b.display_title for b in bar.bookmarks]
    assert titles == [t for t in reversed(sorted(titles, key=lambda s: (s.casefold(), s)))]


def test_sort_tree_retain_keeps_order():
    tree = build_tree(load_bookmarks("sample_chrome.html"))
    before = [b.title for b in tree.iter_bookmarks()]
    sort_tree(tree, mode="retain")
    after = [b.title for b in tree.iter_bookmarks()]
    assert before == after


def test_prune_empty_folders():
    root = load_parsed("sample_firefox.html")
    removed = prune_empty_folders(root)
    assert removed == 1
    assert all(f.name != "Empty folder" for f in root.iter_folders())
    names = [f.name for f in root.folders]
    assert "menu" in names


def test_prune_can_keep_empty():
    root = load_parsed("sample_firefox.html")
    removed = prune_empty_folders(root, keep_empty=True)
    assert removed == 0
    assert any(f.name == "Empty folder" for f in root.iter_folders())
