"""Command line interface for bookmark-tidy."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .analysis import (
    DEFAULT_SIMILARITY,
    DEAD_FLAGS,
    FLAG_LABELS,
    TwinPair,
    find_https_twins,
    find_similar_names,
    find_url_duplicates,
    url_flags,
)
from .interactive import Reviewer, fmt_add_date, trunc
from .models import Bookmark
from .parser import parse_html, read_text
from .treeops import build_tree, prune_empty_folders, sort_tree
from .writers import bookmarks_html, bookmarks_markdown, write_json_report

VERSION = "1.0.0"
TOOL = "bookmark-tidy"

KEEP_POLICIES = ("first", "newest", "shortest-title", "longest-title")


@dataclass
class Stats:
    drops: set = field(default_factory=set)
    upgrades: list = field(default_factory=list)
    merged: int = 0
    keep_all_dups: int = 0
    keep_all_names: int = 0
    names_resolved: int = 0
    dup_dropped: int = 0
    twin_dropped: int = 0
    local_dropped: int = 0
    insecure_dropped: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL,
        description=(
            "Calm a chaotic browser bookmark export: dedupe by URL, review merges, "
            "sort into a clean folder tree, flag file:// and http-only links, and "
            "write an import-ready HTML file plus an LLM-friendly Markdown index. "
            "Nothing is changed in your browser: importing is a separate, deliberate step."
        ),
    )
    parser.add_argument("input", help="browser bookmark export as HTML (Netscape format)")
    parser.add_argument("-o", "--out-dir", default="tidy_output", help="output directory (default: tidy_output)")
    parser.add_argument("--html-name", default="bookmarks_tidy.html", help=argparse.SUPPRESS)
    parser.add_argument("--md-name", default="bookmarks_index.md", help=argparse.SUPPRESS)
    parser.add_argument("--no-report", action="store_true", help=argparse.SUPPRESS)
    inter = parser.add_mutually_exclusive_group()
    inter.add_argument("-y", "--yes", action="store_true", help="run non-interactively and accept defaults everywhere")
    inter.add_argument("-i", "--interactive", action="store_true", help="force the interactive review even without a terminal")
    parser.add_argument("--keep", choices=list(KEEP_POLICIES), default="first", help="which duplicate copy to keep automatically (default: first)")
    parser.add_argument("--sort", choices=["alpha", "retain"], default="alpha", help="sort folders and links alphabetically or keep the original order (default: alpha)")
    parser.add_argument("--reverse", action="store_true", help="reverse the alphabetical sort")
    parser.add_argument("--keep-empty-folders", action="store_true", help="keep folders that hold no links")
    parser.add_argument("--upgrade-http", action="store_true", help="drop http:// copies whose https:// twin already exists")
    parser.add_argument("--drop-local-links", action="store_true", help="drop file:// and localhost/private-address copies")
    parser.add_argument("--drop-insecure-http", action="store_true", help="drop plain http:// copies that have no https twin")
    parser.add_argument("-q", "--quiet", action="store_true", help="print less")
    parser.add_argument("--version", action="version", version=f"{TOOL} {VERSION}")
    return parser


def policy_index(policy: str, items: list[Bookmark]) -> int:
    if policy == "newest":
        return max(range(len(items)), key=lambda i: items[i].add_date or 0)
    if policy == "shortest-title":
        return min(range(len(items)), key=lambda i: (len(items[i].display_title), i))
    if policy == "longest-title":
        return max(range(len(items)), key=lambda i: (len(items[i].display_title), -i))
    return 0


def merge_copies(base: Bookmark, copies: list[Bookmark]) -> None:
    best = max(copies, key=lambda c: (len(c.display_title), -c.order))
    base.title = best.title
    earliest = min((c.add_date for c in copies if c.add_date is not None), default=None)
    if base.add_date is None and earliest is not None:
        base.add_date = earliest
    if base.icon is None:
        base.icon = next((c.icon for c in copies if c.icon), None)
    if base.desc is None:
        base.desc = next((c.desc for c in copies if c.desc), None)


def describe_copy(index: int, bookmark: Bookmark) -> str:
    bits = f"[{bookmark.path_text()}] {bookmark.display_title}"
    when = fmt_add_date(bookmark.add_date)
    if when:
        bits += f" (added {when})"
    if bookmark.flags:
        bits += f" (flagged: {', '.join(bookmark.flags)})"
    return f"  {index}) {bits}"


def _auto_keep_from_group(items: list[Bookmark], keeper: Bookmark, stats: Stats) -> None:
    for item in items:
        if item is not keeper:
            stats.drops.add(item)
            stats.dup_dropped += 1


def review_duplicates(reviewer: Reviewer, groups, args, stats: Stats) -> None:
    live = reviewer.interactive and not reviewer.quitting
    for gi, group in enumerate(groups, 1):
        items = group.items
        default = policy_index(args.keep, items)
        if not (reviewer.interactive and not reviewer.quitting):
            _auto_keep_from_group(items, items[default], stats)
            continue
        if gi == 1:
            print()
            print(f"Reviewing duplicate URLs: {len(groups)} group(s).")
            print("(Enter accepts the recommendation, a = keep all copies, m = merge titles, q = stop reviewing)")
        print()
        print(f"Duplicate URL {gi} of {len(groups)}: {len(items)} copies share:")
        print(f"      {trunc(group.key)}")
        for i, item in enumerate(items, 1):
            print(describe_copy(i, item))
        print(f"  Recommended copy: {default + 1}")
        while True:
            raw = reviewer.prompt(f"  Keep copy? [1-{len(items)}] counts, [a] all, [m] merge, [q] stop (Enter = {default + 1}): ")
            low = raw.lower()
            if low == "":
                _auto_keep_from_group(items, items[default], stats)
                break
            if low in ("a", "all"):
                stats.keep_all_dups += 1
                print("  kept: all copies stay")
                break
            if low in ("m", "merge"):
                merge_copies(items[default], items)
                _auto_keep_from_group(items, items[default], stats)
                stats.merged += 1
                break
            if low.isdigit() and 1 <= int(low) <= len(items):
                _auto_keep_from_group(items, items[int(low) - 1], stats)
                break
            print("  Didn't catch that: a number, 'a', 'm', or 'q'.")


def review_twins(reviewer: Reviewer, twins: list[TwinPair], args, stats: Stats) -> None:
    live = reviewer.interactive and not reviewer.quitting
    for twin in twins:
        insecure, secure = twin.insecure, twin.secure
        if insecure in stats.drops:
            continue
        if not live:
            if args.upgrade_http:
                stats.drops.add(insecure)
                stats.upgrades.append((insecure.url, secure.url))
                stats.twin_dropped += 1
            continue
        print()
        print("Insecure http:// link whose https:// twin already exists in this export:")
        print(describe_copy(1, insecure))
        print(f"       twin: {trunc(secure.url)}")
        print("  Upgrading removes the http copy; the https copy is the one that stays.")
        raw = reviewer.prompt("  [u]pgrade (Enter) / [k]eep http copy / [r]emove: ", quit_default="k")
        low = raw.lower()
        if low in ("", "u", "upgrade"):
            stats.drops.add(insecure)
            stats.upgrades.append((insecure.url, secure.url))
            stats.twin_dropped += 1
        elif low in ("r", "remove"):
            stats.drops.add(insecure)
        elif low in ("k", "keep"):
            pass
        else:
            print("  Kept as-is (unrecognized answer).")


def review_flags(reviewer: Reviewer, rows: list[tuple[str, Bookmark]], args, stats: Stats) -> None:
    batch: str | None = None
    for kind, bookmark in rows:
        if bookmark in stats.drops:
            continue
        live = reviewer.interactive and not reviewer.quitting
        if not live:
            if kind == "local" and args.drop_local_links:
                stats.drops.add(bookmark)
                stats.local_dropped += 1
            elif kind == "insecure" and args.drop_insecure_http:
                stats.drops.add(bookmark)
                stats.insecure_dropped += 1
            continue
        if batch == "remove":
            if kind == "local":
                stats.local_dropped += 1
            else:
                stats.insecure_dropped += 1
            stats.drops.add(bookmark)
            continue
        if batch == "keep":
            continue
        print()
        print("Dead-looking link: it will not work from an import on a normal machine.")
        print(describe_copy(1, bookmark))
        raw = reviewer.prompt("  [k]eep (Enter) / [r]emove / [x] remove all remaining / [s] keep all remaining: ", quit_default="k")
        low = raw.lower()
        if low in ("r", "remove", "x"):
            stats.drops.add(bookmark)
            if kind == "local":
                stats.local_dropped += 1
            else:
                stats.insecure_dropped += 1
            if low == "x":
                batch = "remove"
        elif low in ("s",):
            batch = "keep"
        elif low in ("", "k", "keep"):
            pass
        else:
            print("  Kept as-is (unrecognized answer).")


def review_similar_names(reviewer: Reviewer, groups, stats: Stats) -> None:
    for group in groups:
        live_items = [b for b in group.items if b not in stats.drops]
        if len(live_items) < 2:
            continue
        live = reviewer.interactive and not reviewer.quitting
        if not live:
            stats.keep_all_names += 1
            continue
        print()
        print("Near-duplicate names on different URLs - twins or siblings?")
        for i, item in enumerate(live_items, 1):
            print(describe_copy(i, item))
        raw = reviewer.prompt("  Keep one (removes others): [1-n], or [Enter] keep all: ", quit_default="")
        low = raw.lower()
        if low.isdigit() and 1 <= int(low) <= len(live_items):
            pick = int(low) - 1
            for i, item in enumerate(live_items):
                if i != pick:
                    stats.drops.add(item)
            stats.names_resolved += 1
        elif low == "":
            stats.keep_all_names += 1
        else:
            print("  Kept all (unrecognized answer).")


def manual_flag_rows(bookmarks, twins: list[TwinPair], drops: set) -> list[tuple[str, Bookmark]]:
    twinned_ids = {id(twin.insecure) for twin in twins}
    rows: list[tuple[str, Bookmark]] = []
    for bookmark in bookmarks:
        if bookmark in drops:
            continue
        flags = set(bookmark.flags)
        if flags & {"local-file", "local-address"}:
            rows.append(("local", bookmark))
        elif "insecure-http" in flags and id(bookmark) not in twinned_ids:
            rows.append(("insecure", bookmark))
    return rows


def run(args) -> int:
    input_path = Path(args.input)
    try:
        text, encoding = read_text(input_path)
    except (OSError, MemoryError, ValueError) as exc:
        print(f"error: could not read {input_path}: {exc}", file=sys.stderr)
        return 2

    root, notes = parse_html(text)
    bookmarks = list(root.iter_bookmarks())
    for i, bookmark in enumerate(bookmarks):
        bookmark.order = i
        bookmark.flags = url_flags(bookmark.url)

    def say(message: str) -> None:
        if not args.quiet:
            print(message)

    say(f"Read {input_path} ({encoding}): {len(bookmarks)} bookmark(s).")
    for note in notes:
        say(f"  note: {note}")
    if not bookmarks:
        say("No bookmarks found. I'll still write the output files so the folder is ready.")

    dup_groups = find_url_duplicates(bookmarks)
    twins = find_https_twins(bookmarks)
    similar_groups = find_similar_names(bookmarks)

    interactive = args.interactive or (not args.yes and sys.stdin.isatty())
    reviewer = Reviewer(interactive=interactive)
    stats = Stats()

    review_duplicates(reviewer, dup_groups, args, stats)
    review_twins(reviewer, twins, args, stats)
    review_flags(reviewer, manual_flag_rows(bookmarks, twins, stats.drops), args, stats)
    review_similar_names(reviewer, similar_groups, stats)

    kept = [b for b in bookmarks if b not in stats.drops]
    tree = build_tree(kept)
    sort_tree(tree, mode=args.sort, reverse=args.reverse)
    pruned = prune_empty_folders(tree, keep_empty=args.keep_empty_folders)

    out_dir = Path(args.out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / args.html_name
        md_path = out_dir / args.md_name
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        html_path.write_text(bookmarks_html(tree), encoding="utf-8")
        md_path.write_text(bookmarks_markdown(tree, generated_at=generated), encoding="utf-8")
        report_path: Path | None = None
        if not args.no_report:
            report_path = out_dir / "tidy_report.json"
            report = build_report(
                args, input_path, bookmarks, notes, dup_groups, twins,
                similar_groups, stats, html_path, md_path, report_path, kept, pruned,
            )
            write_json_report(report, report_path)
    except OSError as exc:
        print(f"error: could not write output: {exc}", file=sys.stderr)
        return 1

    say("")
    say("All tidy. Here's the count:")
    say(f"  parsed bookmarks      : {len(bookmarks)}")
    say(f"  duplicate copies cut  : {stats.dup_dropped}")
    say(f"  groups kept whole     : {stats.keep_all_dups} (you chose 'keep all')")
    say(f"  titles merged         : {stats.merged}")
    say(f"  http -> https handled : {stats.twin_dropped}")
    say(f"  local links removed   : {stats.local_dropped}")
    say(f"  plain http removed    : {stats.insecure_dropped}")
    say(f"  name clusters resolved: {stats.names_resolved} (kept as-is: {stats.keep_all_names})")
    say(f"  final link count      : {len(kept)}")
    say("")
    say("Wrote:")
    say(f"  {html_path}  <- import this in your browser when you're ready")
    say(f"  {md_path}  <- paste-ready index for any LLM chat")
    if report_path is not None:
        say(f"  {report_path}  <- full details")
    say("")
    say("Nothing changed in your browser. Import the tidy HTML file on purpose when you're ready.")
    return 0


def build_report(args, input_path, bookmarks, notes, dup_groups, twins, similar_groups, stats, html_path, md_path, report_path, kept, pruned) -> dict:
    flag_counts: dict[str, int] = {}
    for bookmark in bookmarks:
        for flag in bookmark.flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    dup_examples = []
    for group in dup_groups[:20]:
        survivors = [b for b in group.items if b not in stats.drops]
        dropped = [b for b in group.items if b in stats.drops]
        dup_examples.append(
            {
                "url": group.key,
                "copies": len(group.items),
                "kept": [b.display_title for b in survivors],
                "dropped": [b.display_title for b in dropped],
                "dead_looking_flags": sorted(
                    {f for b in group.items for f in b.flags if f in DEAD_FLAGS}
                ),
            }
        )
    twin_examples = [{"http": t.insecure.url, "https": t.secure.url} for t in twins[:20]]
    similar_examples = [[b.display_title for b in g.items] for g in similar_groups[:20]]

    dead_items = []
    seen = set()
    for bookmark in bookmarks:
        if bookmark.flags and id(bookmark) not in seen:
            seen.add(id(bookmark))
            dead_items.append(
                {
                    "title": bookmark.display_title,
                    "url": bookmark.url,
                    "flags": bookmark.flags,
                    "flag_meanings": [FLAG_LABELS.get(f, f) for f in bookmark.flags],
                }
            )

    return {
        "tool": f"{TOOL} {VERSION}",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {
            "path": str(input_path),
            "bookmarks_parsed": len(bookmarks),
            "parser_notes": notes,
        },
        "duplicates": {
            "groups": len(dup_groups),
            "copies_dropped": stats.dup_dropped,
            "policy": args.keep,
            "keep_all_groups": stats.keep_all_dups,
            "merged_groups": stats.merged,
            "examples": dup_examples,
        },
        "https_twins": {
            "pairs": len(twins),
            "upgraded": stats.twin_dropped,
            "examples": twin_examples,
        },
        "dead_looking_flags": {
            "counts": flag_counts,
            "labels": FLAG_LABELS,
            "items": dead_items,
        },
        "near_duplicate_names": {
            "groups": len(similar_groups),
            "resolved": stats.names_resolved,
            "kept_as_is": stats.keep_all_names,
            "threshold": DEFAULT_SIMILARITY,
            "examples": similar_examples,
        },
        "outputs": {
            "html": str(html_path),
            "markdown": str(md_path),
            "report": str(report_path),
        },
        "final": {
            "bookmarks_kept": len(kept),
            "empty_folders_removed": pruned,
        },
        "reminder": "Nothing was changed in your browser. Import the HTML file on purpose when ready.",
    }


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("(stopped)", file=sys.stderr)
        return 130
