"""Talk to the scribe from a terminal, no Switch needed. Handy for development and for
recording a fallback demo.

    python -m scribe.cli            # interactive, you are "Owner"
    python -m scribe.cli Ravi       # interactive as Ravi
"""
from __future__ import annotations

import os
import sys

from .commands import handle
from .store import Ledger


def main() -> None:
    who = sys.argv[1] if len(sys.argv) > 1 else "Owner"
    ledger = Ledger(os.environ.get("SCRIBE_DB", "memory.db"))
    print(f"scribe ready, you are {who}. Type 'help'. Ctrl-D to quit.")
    try:
        for line in sys.stdin if not sys.stdin.isatty() else iter(lambda: input("> "), None):
            line = line.strip()
            if line:
                print(handle(ledger, who, line))
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
