import pytest

from scribe.commands import handle, parse_remember
from scribe.store import Ledger


@pytest.fixture
def ledger():
    return Ledger(":memory:")


def test_parse_remember_extracts_tags_kind_and_deps():
    text, kind, tags, deps = parse_remember("machine 3 trips the breaker when overloaded #machine-3 !observation ^2")
    assert text == "machine 3 trips the breaker when overloaded"
    assert kind == "observation"
    assert tags == ["machine-3"]
    assert deps == [2]


def test_remember_then_recall_roundtrip(ledger):
    r = handle(ledger, "Ravi", "@scribe remember: machine 3 trips the breaker when overloaded #machine-3")
    assert r.startswith("Noted as #1")
    r = handle(ledger, "Meena", "@scribe recall machine 3 breaker")
    assert "trips the breaker" in r
    assert "by Ravi" in r


def test_replace_keeps_old_on_record(ledger):
    handle(ledger, "Owner", "scribe remember: refunds up to 200 need no approval !rule #refund")
    r = handle(ledger, "Owner", "scribe replace #1: refunds up to 100 need no approval")
    assert "#1 is now replaced by #2" in r
    r = handle(ledger, "Ravi", "scribe history #2")
    assert "up to 200" in r and "up to 100" in r


def test_retract_warns_about_dependents(ledger):
    handle(ledger, "Ravi", "scribe remember: machine 3 safe below 8kg !decision")
    handle(ledger, "Owner", "scribe remember: staff may load 8kg without asking !rule ^1")
    r = handle(ledger, "Owner", "scribe retract #1 it overheated")
    assert "Re-check" in r and "#2" in r


def test_blast_command(ledger):
    handle(ledger, "Ravi", "scribe remember: a")
    handle(ledger, "Ravi", "scribe remember: b ^1")
    assert "#2" in handle(ledger, "Ravi", "scribe blast #1")
    assert handle(ledger, "Ravi", "scribe blast #2") == "Nothing depends on #2."


def test_rules_listing(ledger):
    assert "No rules" in handle(ledger, "Owner", "scribe rules")
    handle(ledger, "Owner", "scribe remember: close at 10pm !rule")
    assert "close at 10pm" in handle(ledger, "Owner", "scribe rules")


def test_errors_become_friendly_replies_not_exceptions(ledger):
    assert "Couldn't do that" in handle(ledger, "Ravi", "scribe blast #99")
    assert "Which entry?" in handle(ledger, "Ravi", "scribe replace please")
    assert "didn't catch" in handle(ledger, "Ravi", "scribe sing me a song")
    # a plain-English question addressed to the scribe searches memory instead of failing
    ledger.remember("Ravi", "Washer 3 stops with error E21 when the load is over 10kg", kind="observation", tags=["washer"])
    assert "E21" in handle(ledger, "triager", "@scribe Washer 3 stopped mid-cycle. Have we seen this before?")
    # a mid-sentence mention (typical of an agent's prose) must not trigger help spam
    assert handle(ledger, "triager", "I've asked @scribe whether we've seen this before.") == ""


def test_empty_message_shows_help(ledger):
    assert "I keep the shop's memory" in handle(ledger, "Ravi", "@scribe")
