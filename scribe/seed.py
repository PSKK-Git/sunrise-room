"""Seed the memory with the shop's earlier weeks, so the demo starts with history.

This is DEMO DATA. The README says so: judges should know the first entries were
loaded, and that everything after them is recorded live by people and agents in the room.
"""
from __future__ import annotations

import os

from .store import Ledger

HISTORY = [
    # who, kind, text, tags, depends_on (1-based positions in this list)
    ("Ravi",  "observation", "Washer 3 stops with error E21 when the load is over 10kg", ["machine-3", "washer"], []),
    ("Ravi",  "fix",         "Switching washer 3 off for ten minutes clears E21; if it comes back the same day, call the technician", ["machine-3", "washer"], [1]),
    ("Owner", "rule",        "Any refund needs the owner's approval before money is returned", ["refund"], []),
    ("Owner", "decision",    "When a machine faults mid-cycle, offer a free re-wash first and refund only if the customer still wants it", ["refund", "complaint"], [3]),
    ("Meena", "observation", "CleanCo delivers detergent on Tuesdays only; order by Monday evening", ["stock", "detergent"], []),
    ("Owner", "rule",        "Regular customers (10 or more orders) get their re-wash free of charge, first in the queue", ["complaint", "regulars"], [4]),
]


def seed(ledger: Ledger) -> int:
    ids: list[int] = []
    for who, kind, text, tags, deps in HISTORY:
        f = ledger.remember(text, who, kind=kind, tags=tags, depends_on=[ids[d - 1] for d in deps], source_msg="seed")
        ids.append(f.id)
    return len(ids)


if __name__ == "__main__":
    led = Ledger(os.environ.get("SCRIBE_DB", "memory.db"))
    print(f"seeded {seed(led)} entries")
