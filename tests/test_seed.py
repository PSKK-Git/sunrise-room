from scribe.seed import HISTORY, seed
from scribe.store import Ledger


def test_seed_loads_history_with_dependencies():
    led = Ledger(":memory:")
    assert seed(led) == len(HISTORY)
    assert led.get(2).depends_on == [1]
    assert led.get(6).depends_on == [4]


def test_demo_question_finds_the_first_incident():
    led = Ledger(":memory:")
    seed(led)
    hits = led.recall("washer 3 error E21 stopped", tags=["machine-3"])
    assert hits[0].id in (1, 2)
    assert any("technician" in h.text for h in hits)


def test_question_filler_words_do_not_pull_in_unrelated_rules():
    led = Ledger(":memory:")
    seed(led)
    hits = led.recall("have we seen washer 3 error E21 before", tags=["machine-3"])
    assert 3 not in [h.id for h in hits]


def test_changing_the_refund_decision_shows_what_to_recheck():
    led = Ledger(":memory:")
    seed(led)
    # blast radius of the "free re-wash first" decision includes the regulars rule
    assert [f.id for f in led.blast_radius(4)] == [6]
    # and of the refund approval rule: the decision and, through it, the regulars rule
    assert [f.id for f in led.blast_radius(3)] == [4, 6]


def test_source_is_kept_for_every_seeded_entry():
    led = Ledger(":memory:")
    seed(led)
    assert all(led.get(i).source_who and led.get(i).source_msg == "seed" for i in range(1, 7))
