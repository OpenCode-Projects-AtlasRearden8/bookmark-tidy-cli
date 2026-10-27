import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_cli(args, stdin: str | None = None):
    return subprocess.run(
        [sys.executable, "-m", "bookmark_tidy", *[str(a) for a in args]],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
