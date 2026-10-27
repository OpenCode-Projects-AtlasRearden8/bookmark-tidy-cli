# bookmark-tidy

Your bookmarks folder leaked into a hundred files and four folders named "New Folder (2)".
**bookmark-tidy** is a tiny command-line tool (pure Python, standard library only) that calms a chaotic
browser bookmark export:

- **Parse** Netscape-style bookmark HTML (Chrome, Firefox, Edge, Brave exports)
- **Dedupe by URL** - two copies of the same link keep one seat (you pick which in review)
- **Detect dead-looking links** - `file://` links that only work on one machine, `http://` (insecure)
  copies whose `https://` twin already exists, localhost/private addresses, odd schemes
- **Detect near-duplicate names** - titles so similar they're probably the same site
- **Interactive review** - approve each merge, or answer `q` once and take the defaults for the rest
- **Sort into a consistent folder tree** - folders first, then links, everything alphabetical
  (or keep your original order with `--sort retain`)
- **Write clean outputs**: an import-ready `bookmarks_tidy.html` plus a plain
  `bookmarks_index.md` you can paste into any LLM chat or notes app
- **Explain itself** - a `tidy_report.json` records every decision it made

And the most important line in this README: **bookmark-tidy never touches your browser.**
It reads an export file and writes new files. Getting the tidy version into your browser
is a separate, deliberate step (you re-import on purpose), so nothing can surprise you.

It pairs well with [local-file-organizer-cli](https://github.com/dylanasdale/local-file-organizer-cli)
- one tool calms your files, this one calms your bookmarks.

## The one true quick start

Export bookmarks from your browser (Chrome: *Bookmark manager > ... > Export bookmarks*), then:

```bash
python -m bookmark_tidy bookmarks.html   # try python3 if your system prefers it
```

If your terminal is interactive you'll get a friendly review; otherwise everything
runs on safe defaults. Add `--yes` to force defaults, `-i` to force the review.

Outputs land in `tidy_output/` by default:

| File | What it is |
| --- | --- |
| `bookmarks_tidy.html` | Clean Netscape HTML - import this in your browser when ready |
| `bookmarks_index.md` | Markdown index - readable by humans and by any LLM chat |
| `tidy_report.json` | Every duplicate, flag, and decision, recorded |

## What "dead-looking" means

bookmark-tidy is deliberately cautious: it will not guess whether a link is truly dead
(that needs network checks, and this tool stays fully offline). It flags links that are
*dead on arrival* no matter how healthy the web is:

| Flag | Meaning |
| --- | --- |
| `local-file` | A `file://` link pinpointing a file path on whichever machine made the export |
| `local-address` | `localhost`, `127.0.0.1`, private LAN addresses - works only on that machine |
| `insecure-http` | Plain `http://`; often dead in practice, and private when it's not |
| `missing-scheme` / `odd-scheme` / `browser-internal` | `example.com/..` with no scheme, `javascript:`/other odd links, `chrome://` pages |
| `missing-url` | An empty link (yes, browsers export these) |

An `http://` link whose `https://` twin already exists is your best bet for an upgrade:
review offers to drop the http copy, keeping the secure one. Nothing happens without your OK.

## The interactive review

Example of what a duplicate group looks like during review:

```text
Duplicate URL 1 of 2: 2 copies share:
      https://www.python.org/
  1) [Bookmarks bar] Python Home (added 2023-01-01)
  2) [Other bookmarks] Python (official) (added 2023-01-02)
  Recommended copy: 1
  Keep copy? [1-2] counts, [a] all, [m] merge, [q] stop (Enter = 1):
```

- **Enter / a number** keeps exactly one copy, exactly as-is
- **a** keeps every copy of that URL (your call - it overrides deduping for that group)
- **m** keeps one link but rescues the most complete title among the copies
- **q** stops asking and applies the recommended defaults to everything left

The same "stop and take defaults" safety net covers every prompt: pipe the tool into a
script and it behaves like `--yes`; close the review and nothing destructive runs.

## Options

```text
usage: bookmark-tidy [-h] [-o OUT_DIR] [-y | -i] [--keep {first,newest,shortest-title,longest-title}]
                     [--sort {alpha,retain}] [--reverse] [--keep-empty-folders]
                     [--upgrade-http] [--drop-local-links] [--drop-insecure-http] [-q]
                     [--version]
                     input

positional arguments:
  input                   browser bookmark export as HTML (Netscape format)

options:
  -h, --help              show this help message and exit
  -o, --out-dir OUT_DIR   output directory (default: tidy_output)
  -y, --yes               run non-interactively and accept defaults everywhere
  -i, --interactive       force the interactive review even without a terminal
  --keep POLICY           first | newest | shortest-title | longest-title (default: first)
  --sort MODE             alpha | retain (default: alpha)
  --reverse               reverse the alphabetical sort
  --keep-empty-folders    keep folders that hold no links (default: they go)
  --upgrade-http          drop http:// copies whose https:// twin already exists
  --drop-local-links      drop file:// and localhost/private-address copies
  --drop-insecure-http    drop plain http:// copies with no https twin
  -q, --quiet             print less
  --version               show the version and exit
```

## The Markdown index (made for LLM chats)

The `.md` output is intentionally boring and structured so any LLM chat, notes app,
or static-site tool can read it: one `##` heading per top folder, bold sub-folder
lines, one link per line, flags noted in plain text, and every URL wrapped in
`<...>` so links with parentheses stay intact. Paste the whole file into a chat and
ask "which of these should live in a folder called 'Reading'?" - it will understand.

## How deduping is (cautiously) done

Two bookmarks duplicate each other when their URLs normalize to the same key:
scheme and host are lowercased, fragments (`#...`) are dropped, and a trailing
slash is smoothed `/a/` -> `/a`. Query strings are **not** sorted or stripped,
default ports are **not** merged, and `http` vs `https` are **not** merged
(they surface as twin pairs in review instead). In short: cleanups that are
certainly safe are automatic; everything else is a question you get to answer.

## Development

```bash
python3 -m pytest          # run the test suite (python -m pytest on Windows)
python3 -m bookmark_tidy tests/fixtures/sample_chrome.html --yes -o /tmp/demo
```

Python 3.10+ required. No dependencies to install - `pytest` is the only dev tool,
and the CLI itself uses nothing beyond the standard library. The sample exports in
`tests/fixtures/` double as realistic example files if you want to see the review
flow before touching your own data.

## Credits

Built by **Asdale Dynamics, LLC** - the friendly shop behind
[dylanasdale.github.io](https://dylanasdale.github.io) and *The Massive AI Manual*,
where AI is explained the way a friend would: plain English, step by step, never condescending.

## License

MIT - see [LICENSE](LICENSE). `Copyright (c) 2026 Asdale Dynamics, LLC`
