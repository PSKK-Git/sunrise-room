"""Room Memory ledger for the laundromat room.

A small bi-temporal store of shop knowledge:

* every entry says WHAT is known, WHO said it (person or agent) and in WHICH
  room message,
* every entry has a validity window (valid_from / valid_to) separate from
  when we recorded it (recorded_at), so a rule can be superseded without
  being deleted,
* entries can declare what they depend on, so a wrong decision can be traced
  to everything built on top of it (blast radius).

Pure standard library (sqlite3) so the repo runs anywhere with Python 3.10+.
The same schema maps onto a graph (FalkorDB) if we choose to swap the backend.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

KINDS = ("decision", "rule", "incident", "observation", "fix")

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    text          TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '',
    source_who    TEXT NOT NULL,
    source_msg    TEXT NOT NULL DEFAULT '',
    valid_from    REAL NOT NULL,
    valid_to      REAL,
    recorded_at   REAL NOT NULL,
    superseded_by INTEGER REFERENCES facts(id),
    retracted     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS deps (
    fact_id     INTEGER NOT NULL REFERENCES facts(id),
    depends_on  INTEGER NOT NULL REFERENCES facts(id),
    PRIMARY KEY (fact_id, depends_on)
);
CREATE INDEX IF NOT EXISTS idx_facts_valid ON facts(valid_to);
"""

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    ("a an and are as at be by for from has have in is it of on or that the this to was we with "
     "before seen about know do did does any").split()
)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


@dataclass
class Fact:
    id: int
    kind: str
    text: str
    tags: list[str]
    source_who: str
    source_msg: str
    valid_from: float
    valid_to: Optional[float]
    recorded_at: float
    superseded_by: Optional[int]
    retracted: bool
    depends_on: list[int] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.valid_to is None and not self.retracted

    def to_dict(self) -> dict:
        return asdict(self)


def _row_to_fact(row: sqlite3.Row, deps: Iterable[int]) -> Fact:
    return Fact(
        id=row["id"],
        kind=row["kind"],
        text=row["text"],
        tags=[t for t in row["tags"].split(",") if t],
        source_who=row["source_who"],
        source_msg=row["source_msg"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        recorded_at=row["recorded_at"],
        superseded_by=row["superseded_by"],
        retracted=bool(row["retracted"]),
        depends_on=sorted(deps),
    )


class MemoryError_(ValueError):
    """Raised for invalid memory operations (unknown id, bad kind, ...)."""


class Ledger:
    def __init__(self, path: str = ":memory:", clock=time.time):
        # The agent handles messages on worker threads; callers serialise access with a lock.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._clock = clock

    # ------------------------------------------------------------------ write
    def remember(
        self,
        text: str,
        who: str,
        kind: str = "observation",
        tags: Iterable[str] = (),
        source_msg: str = "",
        depends_on: Iterable[int] = (),
        valid_from: Optional[float] = None,
    ) -> Fact:
        text = text.strip()
        if not text:
            raise MemoryError_("nothing to remember: text is empty")
        if kind not in KINDS:
            raise MemoryError_(f"kind must be one of {', '.join(KINDS)}")
        if not who.strip():
            raise MemoryError_("every entry needs a source (who said it)")
        deps = sorted(set(int(d) for d in depends_on))
        for d in deps:
            self._require(d)
        now = self._clock()
        tag_str = ",".join(sorted({t.strip().lower() for t in tags if t.strip()}))
        cur = self._db.execute(
            "INSERT INTO facts(kind,text,tags,source_who,source_msg,valid_from,recorded_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (kind, text, tag_str, who.strip(), source_msg, valid_from or now, now),
        )
        fid = cur.lastrowid
        for d in deps:
            self._db.execute("INSERT INTO deps(fact_id,depends_on) VALUES (?,?)", (fid, d))
        self._db.commit()
        return self.get(fid)

    def supersede(
        self,
        old_id: int,
        text: str,
        who: str,
        kind: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        source_msg: str = "",
    ) -> Fact:
        """Replace an entry. The old one stays on record, marked as no longer valid."""
        old = self._require(old_id)
        if not old.active:
            raise MemoryError_(f"#{old_id} is not active (already superseded or retracted)")
        new = self.remember(
            text,
            who,
            kind=kind or old.kind,
            tags=old.tags if tags is None else tags,
            source_msg=source_msg,
            depends_on=old.depends_on,
        )
        now = self._clock()
        self._db.execute(
            "UPDATE facts SET valid_to=?, superseded_by=? WHERE id=?", (now, new.id, old_id)
        )
        self._db.commit()
        return self.get(new.id)

    def retract(self, fact_id: int, who: str, reason: str = "") -> Fact:
        """Mark an entry as wrong. Kept for audit, never returned by recall."""
        f = self._require(fact_id)
        if f.retracted:
            raise MemoryError_(f"#{fact_id} is already retracted")
        self._db.execute(
            "UPDATE facts SET retracted=1, valid_to=COALESCE(valid_to, ?) WHERE id=?",
            (self._clock(), fact_id),
        )
        self._db.commit()
        if reason:
            self.remember(
                f"Retracted #{fact_id}: {reason}",
                who,
                kind="observation",
                tags=f.tags,
                depends_on=[fact_id],
            )
        return self.get(fact_id)

    # ------------------------------------------------------------------- read
    def get(self, fact_id: int) -> Fact:
        return self._require(fact_id)

    def _require(self, fact_id: int) -> Fact:
        row = self._db.execute("SELECT * FROM facts WHERE id=?", (int(fact_id),)).fetchone()
        if row is None:
            raise MemoryError_(f"no entry #{fact_id}")
        deps = [
            r["depends_on"]
            for r in self._db.execute("SELECT depends_on FROM deps WHERE fact_id=?", (fact_id,))
        ]
        return _row_to_fact(row, deps)

    def _all(self) -> list[Fact]:
        out = []
        for row in self._db.execute("SELECT * FROM facts ORDER BY id"):
            deps = [
                r["depends_on"]
                for r in self._db.execute(
                    "SELECT depends_on FROM deps WHERE fact_id=?", (row["id"],)
                )
            ]
            out.append(_row_to_fact(row, deps))
        return out

    def recall(
        self,
        query: str = "",
        tags: Iterable[str] = (),
        as_of: Optional[float] = None,
        kinds: Iterable[str] = (),
        limit: int = 5,
    ) -> list[Fact]:
        """Entries that were valid at `as_of` (default: now), best match first.

        Scoring is deliberately simple and explainable: shared words with the
        query, a bonus for matching tags, and a small bonus for rules and
        decisions because staff should see those first.
        """
        q = _tokens(query)
        want_tags = {t.strip().lower() for t in tags if t.strip()}
        want_kinds = set(kinds)
        scored: list[tuple[float, Fact]] = []
        for f in self._all():
            if f.retracted:
                continue
            if as_of is None:
                if not f.active:
                    continue
            else:
                if f.valid_from > as_of or (f.valid_to is not None and f.valid_to <= as_of):
                    continue
            if want_kinds and f.kind not in want_kinds:
                continue
            overlap = len(q & (_tokens(f.text) | set(f.tags)))
            tag_hit = len(want_tags & set(f.tags))
            if q or want_tags:
                if overlap == 0 and tag_hit == 0:
                    continue
            score = overlap + 2.0 * tag_hit + (0.25 if f.kind in ("rule", "decision") else 0.0)
            scored.append((score, f))
        scored.sort(key=lambda p: (-p[0], -p[1].recorded_at, -p[1].id))
        return [f for _, f in scored[: max(1, limit)]]

    def history(self, fact_id: int) -> list[Fact]:
        """The whole chain of an entry: oldest version first, newest last."""
        f = self._require(fact_id)
        # walk back to the root
        seen = {f.id}
        root = f
        while True:
            row = self._db.execute(
                "SELECT id FROM facts WHERE superseded_by=?", (root.id,)
            ).fetchone()
            if row is None or row["id"] in seen:
                break
            root = self._require(row["id"])
            seen.add(root.id)
        chain = [root]
        while chain[-1].superseded_by is not None:
            nxt = self._require(chain[-1].superseded_by)
            if nxt.id in {c.id for c in chain}:
                break
            chain.append(nxt)
        return chain

    def blast_radius(self, fact_id: int) -> list[Fact]:
        """Everything that (transitively) depends on this entry.

        If a decision turns out to be wrong, these are the entries to re-check.
        """
        self._require(fact_id)
        out: list[int] = []
        frontier = [fact_id]
        seen = {fact_id}
        while frontier:
            cur = frontier.pop()
            for row in self._db.execute(
                "SELECT fact_id FROM deps WHERE depends_on=?", (cur,)
            ):
                nid = row["fact_id"]
                if nid not in seen:
                    seen.add(nid)
                    out.append(nid)
                    frontier.append(nid)
        return [self._require(i) for i in sorted(out)]

    def active_rules(self) -> list[Fact]:
        return [f for f in self._all() if f.active and f.kind in ("rule", "decision")]

    # ----------------------------------------------------------------- export
    def dump(self) -> str:
        return json.dumps([f.to_dict() for f in self._all()], indent=2)

    def close(self) -> None:
        self._db.close()


def fmt_time(ts: float) -> str:
    return time.strftime("%d %b %H:%M", time.localtime(ts))


def render_fact(f: Fact, with_source: bool = True) -> str:
    status = "" if f.active else (" [retracted]" if f.retracted else f" [replaced by #{f.superseded_by}]")
    src = f" (by {f.source_who}, {fmt_time(f.valid_from)})" if with_source else ""
    return f"#{f.id} {f.kind}: {f.text}{src}{status}"
