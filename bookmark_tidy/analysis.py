"""Analysis: URL dedupe keys, dead-looking URL flags, and near-duplicate names."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

REVIEWABLE_FLAGS = ("local-file", "local-address", "insecure-http")
DEAD_FLAGS = ("local-file", "local-address", "insecure-http")
FLAG_LABELS = {
    "local-file": "file:// link that only works on one machine",
    "local-address": "localhost or private address",
    "insecure-http": "plain http:// (not https://)",
    "odd-scheme": "unusual link type",
    "missing-scheme": "no web scheme",
    "missing-url": "empty link",
    "malformed-url": "unusual link",
    "browser-internal": "browser-internal page",
}

_LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}
_PRIVATE_PREFIXES = ("127.", "10.", "192.168.")
_APP_SCHEMES = ("chrome", "edge", "brave", "about", "place", "vivaldi")
_ODD_SCHEMES = ("javascript", "data")

_NOISE_ENDINGS = re.compile(r"\s*(official site|official website|home page|homepage)\s*$")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")

DEFAULT_SIMILARITY = 0.87
MAX_ANALYSIS_ITEMS = 25000


def dedupe_key(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    scheme = parts.scheme.lower()
    if scheme in ("http", "https", "ftp", "ws", "wss"):
        try:
            parts.port
        except ValueError:
            return url
        netloc = parts.netloc.lower()
        path = parts.path or "/"
        if len(path) > 1:
            path = path.rstrip("/") or "/"
        return urlunsplit((scheme, netloc, path, parts.query, ""))
    return url


def url_flags(url: str) -> list[str]:
    url = (url or "").strip()
    flags: list[str] = []
    if not url:
        return ["missing-url"]
    try:
        parts = urlsplit(url)
    except ValueError:
        return ["malformed-url"]
    scheme = parts.scheme.lower()
    if scheme == "file":
        flags.append("local-file")
    elif scheme == "http":
        flags.append("insecure-http")
    elif scheme == "":
        flags.append("missing-scheme")
    elif scheme in _APP_SCHEMES:
        flags.append("browser-internal")
    elif scheme in _ODD_SCHEMES:
        flags.append("odd-scheme")
    host = (parts.hostname or "")
    try:
        host = host.lower()
    except ValueError:
        host = ""
    if host and (
        host in _LOCAL_NAMES
        or host.startswith(_PRIVATE_PREFIXES)
        or host.endswith(".local")
    ):
        flags.append("local-address")
    return flags


def is_deal_looking(flags: list[str]) -> bool:
    return bool(set(flags) & set(DEAD_FLAGS))


@dataclass
class DuplicateGroup:
    key: str
    items: list = field(default_factory=list)


@dataclass
class SimilarGroup:
    items: list = field(default_factory=list)


@dataclass
class TwinPair:
    insecure: object
    secure: object


def find_url_duplicates(bookmarks) -> list[DuplicateGroup]:
    buckets: dict[str, list] = defaultdict(list)
    seen: list[str] = []
    for bookmark in bookmarks:
        key = dedupe_key(bookmark.url)
        if not buckets[key]:
            seen.append(key)
        buckets[key].append(bookmark)
    return [DuplicateGroup(key=key, items=buckets[key]) for key in seen if len(buckets[key]) > 1]


def find_https_twins(bookmarks) -> list[TwinPair]:
    secure_keys: dict[str, object] = {}
    for bookmark in bookmarks:
        key = dedupe_key(bookmark.url)
        if key.startswith("https://") and key not in secure_keys:
            secure_keys[key] = bookmark
    twins: list[TwinPair] = []
    seen_insecure = set()
    for bookmark in bookmarks:
        key = dedupe_key(bookmark.url)
        if not key.startswith("http://"):
            continue
        twin_key = "https" + key[4:]
        secure = secure_keys.get(twin_key)
        if secure is not None and secure is not bookmark and id(bookmark) not in seen_insecure:
            twins.append(TwinPair(insecure=bookmark, secure=secure))
            seen_insecure.add(id(bookmark))
    return twins


def normalize_name(title: str) -> str:
    text = (title or "").casefold()
    text = text.replace("&", " and ").replace("+", " plus ")
    text = _NOISE_ENDINGS.sub("", text)
    text = _NONALNUM.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def find_similar_names(bookmarks, threshold: float = DEFAULT_SIMILARITY) -> list[SimilarGroup]:
    count = len(bookmarks)
    if count < 2 or count > MAX_ANALYSIS_ITEMS:
        return []
    normalized = [normalize_name(bookmark.display_title) for bookmark in bookmarks]
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    order = sorted(range(count), key=lambda i: (len(normalized[i]), normalized[i]))
    upper = (2.0 - threshold) / threshold
    for pos, i in enumerate(order):
        li = len(normalized[i])
        if not li:
            continue
        j = pos + 1
        while j < count:
            k = order[j]
            lk = len(normalized[k])
            if not lk:
                j += 1
                continue
            if lk * threshold > li:
                break
            if normalized[i] == normalized[k]:
                union(i, k)
            elif SequenceMatcher(None, normalized[i], normalized[k]).ratio() >= threshold:
                union(i, k)
            j += 1

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(count):
        clusters[find(i)].append(i)
    groups = []
    for root_index in sorted(clusters):
        members = clusters[root_index]
        if len(members) < 2:
            continue
        members.sort()
        groups.append(SimilarGroup(items=[bookmarks[i] for i in members]))
    groups.sort(key=lambda g: (-len(g.items), g.items[0].display_title.casefold()))
    return groups
