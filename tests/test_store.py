import pytest

from scribe.store import Ledger, MemoryError_


class Clock:
    """Deterministic clock so tests can reason about validity windows."""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        self.t += 10
        return self.t


@pytest.fixture
def ledger():
    return Ledger(":memory:", clock=Clock())


def test_remember_and_recall_by_words(ledger):
    ledger.remember("Machine 3 trips the breaker when the drum is overloaded", "Ravi", kind="observation", tags=["machine-3"])
    ledger.remember("Detergent supplier delivers on Tuesdays", "Meena", kind="observation", tags=["stock"])
    hits = ledger.recall("machine 3 overloaded drum")
    assert [h.text for h in hits][0].startswith("Machine 3")
    assert len(hits) == 1


def test_every_entry_needs_a_source(ledger):
    with pytest.raises(MemoryError_):
        ledger.remember("Refunds over 500 need the owner", "  ", kind="rule")


def test_rejects_empty_text_and_bad_kind(ledger):
    with pytest.raises(MemoryError_):
        ledger.remember("   ", "Ravi")
    with pytest.raises(MemoryError_):
        ledger.remember("x", "Ravi", kind="gossip")


def test_supersede_keeps_history_and_hides_old_from_recall(ledger):
    old = ledger.remember("Refunds up to 200 rupees need no approval", "Owner", kind="rule", tags=["refund"])
    new = ledger.supersede(old.id, "Refunds up to 100 rupees need no approval", "Owner")
    assert not ledger.get(old.id).active
    assert ledger.get(old.id).superseded_by == new.id
    texts = [f.text for f in ledger.recall("refunds approval")]
    assert texts == ["Refunds up to 100 rupees need no approval"]
    assert [f.id for f in ledger.history(new.id)] == [old.id, new.id]
    assert [f.id for f in ledger.history(old.id)] == [old.id, new.id]


def test_cannot_supersede_twice(ledger):
    old = ledger.remember("Close at 9pm", "Owner", kind="rule")
    ledger.supersede(old.id, "Close at 10pm", "Owner")
    with pytest.raises(MemoryError_):
        ledger.supersede(old.id, "Close at 11pm", "Owner")


def test_recall_as_of_sees_the_past():
    clock = Clock()
    ledger = Ledger(":memory:", clock=clock)
    old = ledger.remember("Refunds up to 200 need no approval", "Owner", kind="rule", tags=["refund"])
    before_change = clock.t + 1
    ledger.supersede(old.id, "Refunds up to 100 need no approval", "Owner")
    past = ledger.recall("refunds", as_of=before_change)
    now = ledger.recall("refunds")
    assert past[0].text.endswith("200 need no approval")
    assert now[0].text.endswith("100 need no approval")


def test_retracted_entries_are_never_recalled_but_stay_on_record(ledger):
    f = ledger.remember("Machine 5 is fine to run overnight", "Ravi", kind="observation", tags=["machine-5"])
    ledger.retract(f.id, "Owner", reason="it overheated on Friday")
    assert ledger.recall("machine 5 overnight") == [] or all("Retracted" in h.text for h in ledger.recall("machine 5 overnight"))
    assert ledger.get(f.id).retracted


def test_blast_radius_is_transitive(ledger):
    a = ledger.remember("Machine 3 is safe below 8kg", "Ravi", kind="decision")
    b = ledger.remember("Staff may load machine 3 up to 8kg without asking", "Owner", kind="rule", depends_on=[a.id])
    c = ledger.remember("Signs on machine 3 say 8kg max", "Meena", kind="fix", depends_on=[b.id])
    unrelated = ledger.remember("Tuesday delivery", "Meena")
    ids = [f.id for f in ledger.blast_radius(a.id)]
    assert ids == [b.id, c.id]
    assert unrelated.id not in ids
    assert ledger.blast_radius(c.id) == []


def test_blast_radius_unknown_id(ledger):
    with pytest.raises(MemoryError_):
        ledger.blast_radius(999)


def test_dependency_on_unknown_entry_rejected(ledger):
    with pytest.raises(MemoryError_):
        ledger.remember("builds on nothing", "Ravi", depends_on=[42])


def test_tags_boost_ranking(ledger):
    ledger.remember("Check the lint filter weekly", "Ravi", tags=["machine-2"])
    ledger.remember("Machine 2 makes a loud noise when the belt slips", "Ravi", tags=["machine-2"])
    hits = ledger.recall("loud noise", tags=["machine-2"])
    assert hits[0].text.startswith("Machine 2 makes")


def test_rules_ranked_slightly_above_observations(ledger):
    ledger.remember("refund policy observed in practice is generous", "Ravi", kind="observation")
    ledger.remember("refund policy: owner approves above 100", "Owner", kind="rule")
    hits = ledger.recall("refund policy")
    assert hits[0].kind == "rule"


def test_active_rules_lists_only_current_rules_and_decisions(ledger):
    r1 = ledger.remember("Close at 9pm", "Owner", kind="rule")
    ledger.supersede(r1.id, "Close at 10pm", "Owner")
    ledger.remember("It rained today", "Ravi", kind="observation")
    ledger.remember("Use only the blue mop on the floor", "Owner", kind="decision")
    assert sorted(f.text for f in ledger.active_rules()) == ["Close at 10pm", "Use only the blue mop on the floor"]


def test_survives_reopen(tmp_path):
    path = str(tmp_path / "memory.db")
    a = Ledger(path)
    a.remember("Machine 3 trips the breaker when overloaded", "Ravi", kind="observation")
    a.close()
    b = Ledger(path)
    assert b.recall("machine 3 breaker")[0].source_who == "Ravi"
    b.close()
