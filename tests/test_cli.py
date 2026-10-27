import json

from .conftest import FIXTURES, run_cli


def read_report(out):
    return json.loads((out / "tidy_report.json").read_text(encoding="utf-8"))


def test_version():
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert "bookmark-tidy 1.0.0" in result.stdout


def test_help():
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "bookmark" in result.stdout.lower()


def test_missing_input_errors_cleanly(tmp_path):
    result = run_cli(["does-not-exist.html", "--yes", "-o", str(tmp_path / "out")])
    assert result.returncode == 2
    assert "could not read" in result.stderr


def test_conflicting_yes_interactive(tmp_path):
    result = run_cli(["--yes", "--interactive", str(FIXTURES / "empty.html"), "-o", str(tmp_path)])
    assert result.returncode == 2


def test_yes_full_pipeline(tmp_path):
    out = tmp_path / "tidy"
    result = run_cli(
        [
            str(FIXTURES / "sample_chrome.html"),
            "--yes",
            "--upgrade-http",
            "--drop-local-links",
            "-o",
            str(out),
        ]
    )
    assert result.returncode == 0, result.stderr
    html = (out / "bookmarks_tidy.html").read_text(encoding="utf-8")
    md = (out / "bookmarks_index.md").read_text(encoding="utf-8")
    report = read_report(out)

    assert report["input"]["bookmarks_parsed"] == 12
    assert report["duplicates"]["groups"] == 2
    assert report["duplicates"]["copies_dropped"] == 2
    assert report["https_twins"]["pairs"] == 1
    assert report["https_twins"]["upgraded"] == 1
    assert report["final"]["bookmarks_kept"] == 7
    assert report["outputs"]["html"].endswith("bookmarks_tidy.html")

    assert html.count("<DT><A HREF=") == 7
    assert "http://realpython.com" not in html
    assert "https://realpython.com" in html
    assert "recipe.html" not in html
    assert "localhost" not in html
    assert "https://www.python.org/" in html

    assert md.startswith("# Bookmarks")
    assert "## Bookmarks bar" in md
    assert "(flag:" not in md
    assert "7 links in 2 folders" in md
    assert "Import the tidy HTML file on purpose" in result.stdout


def test_yes_keep_longest_title_policy(tmp_path):
    out = tmp_path / "out"
    result = run_cli(
        [str(FIXTURES / "sample_chrome.html"), "--yes", "--keep", "longest-title", "-o", str(out)]
    )
    assert result.returncode == 0
    report = read_report(out)
    kept_titles = {ex["kept"][0] for ex in report["duplicates"]["examples"]}
    assert "Python (official)" in kept_titles
    assert "Example Site Again" in kept_titles


def test_auto_mode_keeps_flagged_links_by_default(tmp_path):
    out = tmp_path / "out"
    result = run_cli([str(FIXTURES / "sample_chrome.html"), "--yes", "-o", str(out)])
    assert result.returncode == 0
    report = read_report(out)
    assert report["final"]["bookmarks_kept"] == 12 - report["duplicates"]["copies_dropped"]
    assert report["https_twins"]["upgraded"] == 0
    html = (out / "bookmarks_tidy.html").read_text(encoding="utf-8")
    assert "file:///home/dylan/notes/recipe.html" in html
    assert "http://localhost:8080" in html
    md = (out / "bookmarks_index.md").read_text(encoding="utf-8")
    assert "*(flag: local-file)*" in md
    assert "*(flag: insecure-http, local-address)*" in md


def test_interactive_quit_early(tmp_path):
    out = tmp_path / "out"
    result = run_cli(
        [str(FIXTURES / "sample_chrome.html"), "-i", "-o", str(out)],
        stdin="q\n",
    )
    assert result.returncode == 0, result.stderr
    assert "keeping the default choice" in result.stdout
    report = read_report(out)
    assert report["duplicates"]["copies_dropped"] == 2
    assert report["https_twins"]["upgraded"] == 0
    assert report["final"]["bookmarks_kept"] == 10


def test_interactive_answers(tmp_path):
    out = tmp_path / "out"
    result = run_cli(
        [str(FIXTURES / "sample_chrome.html"), "-i", "-o", str(out)],
        stdin="\n\nu\nr\nk\n\n\n",
    )
    assert result.returncode == 0, result.stderr
    report = read_report(out)
    assert report["duplicates"]["copies_dropped"] == 2
    assert report["https_twins"]["upgraded"] == 1
    assert report["final"]["bookmarks_kept"] == 8
    html = (out / "bookmarks_tidy.html").read_text(encoding="utf-8")
    assert "recipe.html" not in html
    assert "localhost:8080" in html


def test_empty_fixture_run(tmp_path):
    out = tmp_path / "out"
    result = run_cli([str(FIXTURES / "empty.html"), "--yes", "-o", str(out)])
    assert result.returncode == 0, result.stderr
    report = read_report(out)
    assert report["input"]["bookmarks_parsed"] == 0
    assert "No bookmarks found" in result.stdout
    md = (out / "bookmarks_index.md").read_text(encoding="utf-8")
    assert "0 links" in md


def test_messy_fixture_survives(tmp_path):
    out = tmp_path / "out"
    result = run_cli([str(FIXTURES / "messy.html"), "--yes", "-o", str(out)])
    assert result.returncode == 0, result.stderr
    report = read_report(out)
    assert report["input"]["bookmarks_parsed"] == 9
    assert report["duplicates"]["groups"] == 1
    assert report["final"]["bookmarks_kept"] == 8
    html = (out / "bookmarks_tidy.html").read_text(encoding="utf-8")
    assert "A &amp; B &quot;quoted&quot;" in html


def test_messy_flags_show_up_in_report(tmp_path):
    out = tmp_path / "out"
    result = run_cli([str(FIXTURES / "messy.html"), "--yes", "-o", str(out)])
    assert result.returncode == 0
    report = read_report(out)
    counts = report["dead_looking_flags"]["counts"]
    assert counts.get("odd-scheme") == 1
    assert counts.get("missing-scheme") == 1
    assert counts.get("missing-url") == 1
    items = report["dead_looking_flags"]["items"]
    browser_internal = [i for i in items if "browser-internal" in i["flags"]]
    assert browser_internal and browser_internal[0]["url"] == "chrome://settings/"


def test_retain_sort(tmp_path):
    out = tmp_path / "out"
    result = run_cli(
        [str(FIXTURES / "messy.html"), "--yes", "--sort", "retain", "-o", str(out)]
    )
    assert result.returncode == 0
    html = (out / "bookmarks_tidy.html").read_text(encoding="utf-8")
    assert html.index("Wikipedia") < html.index("Dup Top")
