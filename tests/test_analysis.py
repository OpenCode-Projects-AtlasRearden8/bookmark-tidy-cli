from bookmark_tidy.analysis import (
    DEFAULT_SIMILARITY,
    find_https_twins,
    find_similar_names,
    find_url_duplicates,
    normalize_name,
    url_flags,
)
from bookmark_tidy.models import Bookmark
from bookmark_tidy.parser import parse_html

from .conftest import FIXTURES


def load_chrome():
    return parse_html((FIXTURES / "sample_chrome.html").read_text(encoding="utf-8"))


def sample(title, url, order=0):
    return Bookmark(title=title, url=url, order=order)


def test_dedupe_key_normalization():
    assert find_url_duplicates is not None
    from bookmark_tidy.analysis import dedupe_key

    assert dedupe_key("HTTPS://Example.COM/a/#frag") == "https://example.com/a"
    assert dedupe_key("https://example.com/a/") == "https://example.com/a"
    assert dedupe_key("https://example.com/a?b=1&c=2") == "https://example.com/a?b=1&c=2"
    assert dedupe_key("https://example.com/a?b=1&c=2") != "https://example.com/a"
    assert dedupe_key("http://example.com") != dedupe_key("https://example.com")
    assert dedupe_key("") == ""
    assert dedupe_key("note://write/1") == "note://write/1"


def test_url_flags_buckets():
    assert url_flags("file:///home/me/notes.html") == ["local-file"]
    assert url_flags("http://plain.example.com/page") == ["insecure-http"]
    assert set(url_flags("http://localhost:8080/dev/")) == {"insecure-http", "local-address"}
    assert url_flags("javascript:void(0)") == ["odd-scheme"]
    assert url_flags("chrome://settings/") == ["browser-internal"]
    assert url_flags("") == ["missing-url"]
    assert url_flags("example.com/missing-scheme") == ["missing-scheme"]
    assert url_flags("https://fine.example.com/") == []
    assert "local-address" in url_flags("http://192.168.1.5/router")
    assert "local-address" in url_flags("https://printer.home.local/")


def test_chrome_duplicates_and_twins():
    root, _ = load_chrome()
    bookmarks = list(root.iter_bookmarks())
    dups = find_url_duplicates(bookmarks)
    assert len(dups) == 2
    keys = {g.key for g in dups}
    assert keys == {"https://www.python.org/", "https://example.com/"}
    python_group = next(g for g in dups if "python" in g.key)
    assert [b.title for b in python_group.items] == ["Python Home", "Python (official)"]

    twins = find_https_twins(bookmarks)
    assert len(twins) == 1
    assert twins[0].insecure.url == "http://realpython.com/"
    assert twins[0].insecure.title == "Real Python"
    assert twins[0].secure.url == "https://realpython.com/"


def test_no_twins_without_https_copy():
    root, _ = load_chrome()
    http_only = [b for b in root.iter_bookmarks() if b.url == "http://localhost:8080/dev-server/"]
    others = [b for b in root.iter_bookmarks() if b.url != "http://localhost:8080/dev-server/"]
    assert http_only and len(find_https_twins(http_only)) == 0
    assert len(find_https_twins(http_only + others)) == 1


def test_similar_names_chrome():
    root, _ = load_chrome()
    bookmarks = list(root.iter_bookmarks())
    groups = find_similar_names(bookmarks)
    assert len(groups) == 2
    url_groups = {frozenset(b.url for b in g.items) for g in groups}
    assert frozenset({"https://example.com/", "https://example.com/about"}) in url_groups
    assert (
        frozenset({"https://news.ycombinator.com/", "https://news.ycombinator.com/news"})
        in url_groups
    )


def test_normalize_name_and_threshold():
    assert normalize_name("The Official Site") == "the"
    assert normalize_name("Best GPT Tools 2026!!") == "best gpt tools 2026"

    duo = [sample("Alpha Tool", "https://a.com"), sample("Alpha  Tool", "https://a.org")]
    groups = find_similar_names(duo)
    assert len(groups) == 1 and len(groups[0].items) == 2

    long_gap = [sample("Alpha Tool", "https://a.com"), sample("Alpha Tool Plus More Words", "https://b.com")]
    assert find_similar_names(long_gap) == []

    strangers = [sample("Alpha Tool", "https://a.com"), sample("Completely Different", "https://b.com")]
    assert find_similar_names(strangers) == []


def test_similar_respects_threshold():
    from bookmark_tidy.analysis import find_similar_names as find
    near = [sample("Alpha Tool", "https://a.com"), sample("Alpha Toolz", "https://b.com")]
    assert len(find(near, 0.87)) in (0, 1)
    assert len(find(near, 0.1)) == 1
    far_capped = [sample("x", "https://a.com"), sample("y", "https://b.com")]
    assert find(far_capped, DEFAULT_SIMILARITY) == []
