from bookmark_tidy.parser import parse_html, read_text

from .conftest import FIXTURES


def load(name):
    return parse_html((FIXTURES / name).read_text(encoding="utf-8"))


def test_chrome_counts_and_structure():
    root, notes = load("sample_chrome.html")
    folders, bookmarks = root.counts()
    assert bookmarks == 12
    assert [f.name for f in root.folders] == ["Bookmarks bar", "Other bookmarks"]
    assert [f.name for f in root.folders[0].folders] == ["Python"]
    assert folders == 3
    assert notes == []


def test_bookmark_paths():
    root, _ = load("sample_chrome.html")
    by_title = {b.display_title: b for b in root.iter_bookmarks()}
    assert by_title["Python Docs"].path == ("Bookmarks bar", "Python")
    assert by_title["Python Home"].path == ("Bookmarks bar",)
    assert by_title["Python (official)"].path == ("Other bookmarks",)


def test_description_and_icon_capture():
    root, _ = load("sample_chrome.html")
    by_title = {b.display_title: b for b in root.iter_bookmarks()}
    assert by_title["Python Docs"].desc == "Official Python documentation."
    assert by_title["Real Python"].icon == "data:image/png;base64,AAAA"


def test_add_date_parsing():
    root, _ = load("sample_chrome.html")
    by_title = {b.display_title: b for b in root.iter_bookmarks()}
    assert by_title["Python Home"].add_date == 1672531200


def test_messy_unbalanced_and_unclosed():
    root, notes = load("messy.html")
    all_bm = list(root.iter_bookmarks())
    assert len(all_bm) == 9
    wiki = [b for b in all_bm if b.url == "https://www.wikipedia.org/"]
    assert wiki and wiki[0].title == "Wikipedia"
    assert any("auto-closed" in note for note in notes)
    titles = [b.title for b in all_bm if b.url == "https://example.com/titles"]
    assert titles == ['A & B "quoted"']
    broken = [b for b in all_bm if b.title == "Broken Button"][0]
    assert broken.add_date is None


def test_firefox_empty_folder():
    root, _ = load("sample_firefox.html")
    folders = [f.name for f in root.folders]
    assert "menu" in folders
    empty = [f for f in root.iter_folders() if f.name == "Empty folder"]
    assert len(empty) == 1
    _, bookmarks = root.counts()
    assert bookmarks == 3


def test_empty_fixture():
    root, notes = load("empty.html")
    folders, bookmarks = root.counts()
    assert (folders, bookmarks) == (0, 0)
    assert notes == []


def test_read_text_utf8_bom(tmp_path):
    path = tmp_path / "bom.html"
    path.write_bytes(b"\xef\xbb\xbf<H1>x</H1>")
    text, encoding = read_text(path)
    assert encoding.startswith("utf-8")
    assert "x" in text


def test_read_text_latin_fallback(tmp_path):
    path = tmp_path / "latin.html"
    path.write_bytes(b"<A>caf\xe9</A>")
    text, _ = read_text(path)
    assert "caf\xe9" in text
