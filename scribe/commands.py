"""Chat commands for the scribe. Pure functions: text in, reply text out.

Staff talk to the scribe in the room like this (the agent protocol delivers the
message; see agent.py):

    @scribe remember: machine 3 trips the breaker when overloaded #machine-3 !observation
    @scribe remember: staff may load up to 8kg ^1 !rule
    @scribe replace #4: refunds up to 100 rupees need no approval
    @scribe retract #4 it caused a double refund
    @scribe recall machine 3 breaker
    @scribe blast #1
    @scribe history #4
    @scribe rules

Syntax inside "remember":
    #tag      adds a tag
    !kind     sets the kind (decision, rule, incident, observation, fix)
    ^N        says this entry depends on entry #N (can repeat)
"""
from __future__ import annotations

import re

from .store import KINDS, Ledger, MemoryError_, render_fact

HELP = (
    "I keep the shop's memory. Try:\n"
    "- remember: <what> #tag !rule|decision|incident|observation|fix ^<id it builds on>\n"
    "- replace #<id>: <new text>\n"
    "- retract #<id> <why>\n"
    "- recall <words>\n"
    "- blast #<id>   (what depends on this)\n"
    "- history #<id>\n"
    "- rules"
)

_ID = re.compile(r"#(\d+)")
_TAG = re.compile(r"(?<![\w#])#([A-Za-z][\w-]*)")
_KIND = re.compile(r"!(" + "|".join(KINDS) + r")\b")
_DEP = re.compile(r"\^(\d+)")


def _strip_prefix(text: str, bot_names: tuple[str, ...]) -> str:
    t = text.strip()
    if t.startswith("@"):  # "@scribe", "@scribe:server": drop the whole mention token
        t = t.partition(" ")[2].lstrip(" :,-")
    for name in bot_names:
        for p in (f"@{name}", name):
            if t.lower().startswith(p.lower()):
                t = t[len(p):].lstrip(" :,-")
                break
    return t.strip()


def parse_remember(body: str):
    kind_m = _KIND.search(body)
    kind = kind_m.group(1) if kind_m else "observation"
    deps = [int(x) for x in _DEP.findall(body)]
    tags = _TAG.findall(body)
    text = _KIND.sub("", body)
    text = _DEP.sub("", text)
    text = _TAG.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text, kind, tags, deps


def handle(ledger: Ledger, who: str, message: str, msg_id: str = "", bot_names: tuple[str, ...] = ("scribe",)) -> str:
    """Run one command and return the reply to post in the room."""
    t = _strip_prefix(message, bot_names)
    low = t.lower()
    try:
        if not t or low in ("help", "?"):
            return HELP

        if low.startswith("remember"):
            body = t[len("remember"):].lstrip(" :")
            text, kind, tags, deps = parse_remember(body)
            f = ledger.remember(text, who, kind=kind, tags=tags, source_msg=msg_id, depends_on=deps)
            extra = f" (builds on {', '.join('#'+str(d) for d in deps)})" if deps else ""
            return f"Noted as #{f.id} [{f.kind}]{extra}: {f.text}"

        if low.startswith(("replace", "supersede")):
            m = _ID.search(t)
            if not m:
                return "Which entry? Use: replace #<id>: <new text>"
            body = t[m.end():].lstrip(" :")
            text, kind, tags, _ = parse_remember(body)
            new = ledger.supersede(
                int(m.group(1)), text, who,
                kind=kind if _KIND.search(body) else None,
                tags=tags or None,
                source_msg=msg_id,
            )
            return f"#{m.group(1)} is now replaced by #{new.id}: {new.text} (the old one stays on record)"

        if low.startswith("retract"):
            m = _ID.search(t)
            if not m:
                return "Which entry? Use: retract #<id> <why>"
            reason = t[m.end():].strip(" :")
            ledger.retract(int(m.group(1)), who, reason=reason)
            hit = ledger.blast_radius(int(m.group(1)))
            warn = ""
            if hit:
                warn = " Re-check these, they were built on it: " + "; ".join(f"#{h.id}" for h in hit)
            return f"Retracted #{m.group(1)}.{warn}"

        if low.startswith("blast"):
            m = _ID.search(t)
            if not m:
                return "Which entry? Use: blast #<id>"
            hit = ledger.blast_radius(int(m.group(1)))
            if not hit:
                return f"Nothing depends on #{m.group(1)}."
            return f"If #{m.group(1)} is wrong, re-check:\n" + "\n".join("- " + render_fact(h) for h in hit)

        if low.startswith("history"):
            m = _ID.search(t)
            if not m:
                return "Which entry? Use: history #<id>"
            return "\n".join("- " + render_fact(f) for f in ledger.history(int(m.group(1))))

        if low.startswith("rules"):
            rules = ledger.active_rules()
            if not rules:
                return "No rules or decisions recorded yet."
            return "Current rules and decisions:\n" + "\n".join("- " + render_fact(r) for r in rules)

        if low.startswith(("recall", "what do we know", "have we seen")):
            q = re.sub(r"^(recall|what do we know about|what do we know|have we seen)\b[: ]*", "", t, flags=re.I)
            tags = _TAG.findall(q)
            q = _TAG.sub("", q)
            hits = ledger.recall(q, tags=tags, limit=5)
            if not hits:
                return "Nothing on record about that yet."
            return "Here is what we know:\n" + "\n".join("- " + render_fact(h) for h in hits)

        # Only answer an unknown message that opens with the scribe's name. A mention in the middle of a sentence
        # ("I've asked @scribe whether...") is an agent or person talking about it, not to it: stay silent.
        opens_with_name = any(message.strip().lower().lstrip("@").startswith(n.lower()) for n in bot_names)
        if not opens_with_name:
            return ""
        # Agents ask in plain sentences ("Have we seen this before? ..."), not exact commands: treat the whole
        # message as a memory search, and fall back to the help text only when nothing matches.
        hits = ledger.recall(_TAG.sub("", t), tags=_TAG.findall(t), limit=5)
        if hits:
            return "Here is what we know:\n" + "\n".join("- " + render_fact(h) for h in hits)
        return "I didn't catch that.\n" + HELP
    except MemoryError_ as e:
        return f"Couldn't do that: {e}"
