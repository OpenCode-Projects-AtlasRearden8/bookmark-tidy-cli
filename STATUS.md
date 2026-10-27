# STATUS - bookmark-tidy

Updated: 2026-10-27

## What was built

**bookmark-tidy** - a pure-stdlib (Python 3.10+, no third-party dependencies in the tool
itself) command-line utility that calms a chaotic browser bookmark export:

- Parses Netscape-format bookmark HTML (Chrome / Firefox / Edge / Brave style exports)
- Dedupes by URL with conservative normalization (scheme/host lowercased, fragments dropped,
  trailing slashes smoothed; query strings, default ports, and http-vs-https are NOT merged)
- Flags "dead-looking" links: `file://`, localhost/private addresses, plain `http://`,
  missing schemes, odd schemes (`javascript:`, `data:`), `chrome://` internals, empty links
- Detects http->https twin pairs and offers to upgrade (drop the http copy)
- Detects near-duplicate names across different URLs (difflib similarity, threshold 0.87)
- Interactive review with safe defaults: per-duplicate keep/merge/keep-all, twin upgrades,
  flagged-link keep/remove with batch answers (`x` remove all, `s` keep all), name clusters;
  `q` (or EOF/pipe) stops asking and applies conservative defaults everywhere
- Sorts the tree: folders first, then links, case-insensitive alpha (or `--sort retain`)
- Prunes empty folders (or keeps them with `--keep-empty-folders`)
- Writes:
  - `bookmarks_tidy.html` - import-ready Netscape HTML (CDATEs, icons, descriptions preserved)
  - `bookmarks_index.md` - plain Markdown index readable by humans and any LLM chat,
    with flags noted inline and URLs wrapped in `<...>` so links with parens stay intact
  - `tidy_report.json` - every group, flag, and decision recorded
- Guarantees: **nothing in the browser is ever touched.** The tool reads an export file and
  writes new files; importing the HTML is a separate, deliberate step by the user.

## Layout

```text
bookmark_tidy/
  __init__.py / __main__.py   package + python -m entry
  cli.py                      argparse, review orchestration, summary, report building
  parser.py                   forgiving Netscape HTML parser (unclosed anchors/DL/DD tolerated)
  analysis.py                 dedupe keys, URL flags, https twins, similar-name clustering
  treeops.py                  build/sort/prune folder tree
  interactive.py              Reviewer prompt engine with quit-defaults
  writers.py                  HTML, Markdown, and JSON report writers
tests/
  fixtures/                   sample_chrome.html, sample_firefox.html, messy.html, empty.html
  test_parser.py, test_analysis.py, test_treeops.py, test_writers.py,
  test_interactive.py, test_cli.py (end-to-end subprocess runs)
LICENSE                       MIT, Copyright (c) 2026 Asdale Dynamics, LLC
README.md                     friendly user guide; credits Asdale Dynamics, LLC
pyproject.toml                optional install (console script bookmark-tidy); pytest config
.gitignore                    pycache, tidy_output/, egg-info, etc.
```

## How to run it

```bash
# from this folder, no install needed:
python3 -m bookmark_tidy bookmarks.html            # interactive when in a terminal
python3 -m bookmark_tidy bookmarks.html --yes      # defaults everywhere, no prompts
python3 -m bookmark_tidy bookmarks.html -i         # force interactive review

# handy flags:
#   --keep first|newest|shortest-title|longest-title   auto duplicate policy
#   --sort alpha|retain, --reverse, --keep-empty-folders
#   --upgrade-http, --drop-local-links, --drop-insecure-http
#   -o OUT_DIR (default tidy_output), -q

# optional install (after pip install -e .):
bookmark-tidy bookmarks.html
```

Outputs default to `tidy_output/`: `bookmarks_tidy.html`, `bookmarks_index.md`,
`tidy_report.json`. To get the tidy version into a browser: open the browser's bookmark
manager, choose *Import bookmarks*, and pick the HTML file - on purpose, when ready.

## Verification results

- `python3 -m pytest` -> **49 passed** (parser, analysis, treeops, writers, interactive,
  CLI end-to-end subprocess tests; fixtures in tests/fixtures)
- `python3 -m bookmark_tidy --version` -> `bookmark-tidy 1.0.0`; `--help` clean
- End-to-end on `tests/fixtures/sample_chrome.html` (12 bookmarks: 2 dup groups,
  1 http/https twin, file:// + localhost links, 2 near-name clusters):
  - `--yes --upgrade-http --drop-local-links` -> 7 links kept; http twin dropped,
    https copy kept; recipe.html (file://) and localhost dropped; report matches
  - piped interactive answers (`\n\nu\nr\nk\n\n\n`) -> 8 links kept (recipe removed,
    dev server kept by choice) - prompts verified end-to-end
  - piped `q` -> review stops early, conservative defaults applied, 10 links kept
- `tests/fixtures/messy.html` (unclosed anchors, unbalanced DL, javascript:/scheme-less/
  empty/chrome:// links) -> parsed 9, deduped to 8, no crash, odd flags reported
- `tests/fixtures/empty.html` -> graceful "no bookmarks found", valid empty outputs
- `tests/fixtures/sample_firefox.html` -> empty folder pruned by default, kept with
  `--keep-empty-folders`
- Round trip: written HTML re-parses to the same folder/link counts; titles with
  `<`, `>`, `&`, quotes survive escaping and re-parse
- Optional packaging verified: `pip install -e .` builds and the `bookmark-tidy`
  console script runs (`--version` OK); editable install removed afterwards
- Encoding: UTF-8 (with BOM) and latin-1 fallback both handled

## Known gaps (honest list)

- **No network checks**: "dead-looking" is heuristic (file://, localhost, http-only, odd
  schemes). Truly dead hosts need a link checker; bookmark-tidy deliberately stays offline.
- Duplicate policy can't be applied per-URL non-interactively (interactive mode can;
  `--keep` is one policy for all groups in `--yes` mode).
- Near-duplicate detection compares titles only (not URLs); auto mode never removes
  near-name matches, it only reports them (removal is an interactive choice).
- Folder dates (`LAST_MODIFIED` on H3) are not preserved on export; bookmark icons,
  add dates, and descriptions are.
- Very large exports (tens of thousands of links): URL dedupe is linear, but
  near-name clustering is windowed O(n log n)-ish with pairwise compares; a hard cap
  (25,000 items) skips name clustering for giant files rather than slow down.
- Firefox `TAGS=` attributes are dropped rather than folded into the index.
- No support for importing to a specific browser profile or JSON bookmark formats.

## Compliance notes

- MIT LICENSE included with exactly `Copyright (c) 2026 Asdale Dynamics, LLC`
- README credits Asdale Dynamics, LLC
- Pure standard library; no secrets, API keys, or personal data in any file
  (fixtures use example.com/fixture URLs and a `dylan` username purely as sample text)
- Git initialized locally; plain commit messages, no Co-authored-by trailers,
  no push, no remote, nothing published
