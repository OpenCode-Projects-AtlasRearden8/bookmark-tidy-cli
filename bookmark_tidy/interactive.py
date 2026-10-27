"""Interactive review prompts with safe defaults and quick-exit handling."""
from __future__ import annotations

from datetime import datetime, timezone


class Reviewer:
    def __init__(self, interactive: bool, input_fn=None, out=None):
        self.interactive = interactive
        self.quitting = False
        self._input = input_fn if input_fn is not None else input
        self._out = out if out is not None else print

    def prompt(self, message: str, default: str = "", quit_default: str | None = None) -> str:
        if not self.interactive or self.quitting:
            return default
        shown = message if message.endswith((" ", ":")) else message + " "
        try:
            reply = self._input(shown).strip()
        except (EOFError, KeyboardInterrupt):
            self.quitting = True
            self._out("")
            self._out("(review stopped: keeping the default choice for everything else)")
            return default if quit_default is None else quit_default
        if reply.lower() in ("q", "quit"):
            self.quitting = True
            self._out("(ok: keeping the default choice for everything else)")
            return default if quit_default is None else quit_default
        return reply

    def notes(self) -> None:
        if not self.interactive and not self.quitting:
            return


def fmt_add_date(ts) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return ""


def trunc(url: str, width: int = 88) -> str:
    url = url or ""
    return url if len(url) <= width else url[: width - 1] + "\u2026"
