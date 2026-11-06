"""Frames below follow the Switch docs ("Agent connection", "Agent events"):
domain events are {"event": kind, "data": {room_id, payload, sequence}, "id": sequence}.
"""
import threading

from scribe import wire
from scribe.agent import Scribe
from scribe.store import Ledger


def make():
    sent = []
    s = Scribe(Ledger(":memory:"), lambda room, text: sent.append((room, text)))
    return s, sent


def msg(body, sender_name="Ravi", addressed=True, room="r1", mid="m1", seq=1):
    return {
        "event": "message",
        "data": {
            "type": "message",
            "room_id": room,
            "bridge_id": None,
            "channel_type": None,
            "sequence": seq,
            "payload": {
                "addressed": addressed,
                "sender": "@switch-user-ab12:srv",
                "sender_name": sender_name,
                "message_id": mid,
                "body": body,
                "timestamp": 1730000000000,
                "thread_id": None,
                "attachments": [],
            },
        },
        "id": seq,
    }


def test_connection_state_stores_cursor_and_generation():
    s, _ = make()
    s.on_frame({"event": "connection_state", "data": {"rooms": ["r1"], "cursor": 7, "generation": 3}})
    assert (s.cursor, s.generation, s.rooms) == (7, 3, ["r1"])


def test_connection_state_also_accepted_at_top_level():
    s, _ = make()
    s.on_frame({"type": "connection_state", "rooms": ["r1"], "cursor": 2, "generation": 1})
    assert (s.cursor, s.generation, s.rooms) == (2, 1, ["r1"])


def test_pong_carries_highest_processed_sequence():
    """Regression: pings carry no cursor, so the cursor must come from processed events."""
    s, _ = make()
    s.on_frame({"event": "connection_state", "data": {"cursor": 7}})
    assert s.on_frame({"event": "ping"}) == {"type": "pong", "cursor": 7}
    s.on_frame(msg("@scribe help", seq=12))
    assert s.on_frame({"event": "ping"}) == {"type": "pong", "cursor": 12}
    s.on_frame(msg("@scribe help", seq=9))  # an older replay never moves the cursor back
    assert s.on_frame({"event": "ping"})["cursor"] == 12


def test_only_addressed_messages_are_answered():
    s, sent = make()
    s.on_frame(msg("remember: tuesday delivery", addressed=False))
    assert sent == []
    s.on_frame(msg("@scribe remember: tuesday delivery #stock", seq=2))
    assert len(sent) == 1 and sent[0][0] == "r1" and sent[0][1].startswith("Noted as #1")


def test_real_message_shape_is_parsed():
    """Regression: the old parser looked for addressed/content one level too high."""
    m = wire.parse_message(msg("@scribe rules", sender_name="Owner", room="room-9", mid="mm"))
    assert (m.room_id, m.sender, m.content, m.message_id) == ("room-9", "Owner", "@scribe rules", "mm")


def test_scribe_never_answers_itself():
    s, sent = make()
    s.on_frame(msg("@scribe help", sender_name="scribe"))
    assert sent == []


def test_source_of_entry_is_the_person_who_said_it():
    s, sent = make()
    s.on_frame(msg("@scribe remember: machine 3 trips when overloaded", sender_name="Ravi", mid="m42"))
    fact = s.ledger.get(1)
    assert fact.source_who == "Ravi" and fact.source_msg == "m42"


def test_longer_mention_is_stripped():
    s, sent = make()
    s.on_frame(msg("@scribe:srv remember: delivery is Tuesday"))
    assert sent[0][1].startswith("Noted as #1")


def test_unknown_frames_are_ignored():
    s, sent = make()
    assert s.on_frame({"event": "something_new"}) is None
    assert sent == []


def test_gap_resets_cursor_to_resumed_at():
    s, _ = make()
    s.on_frame({"event": "gap", "data": {"from_sequence": 3, "resumed_at": 40}})
    assert s.cursor == 40


def test_taken_over_is_final_but_lapse_is_not():
    s, _ = make()
    s.on_frame({"event": "evicted", "data": {"code": "heartbeat_lapsed", "reason": "slow"}})
    assert s.stop_reason is None
    s.on_frame({"event": "evicted", "data": {"code": "taken_over", "reason": "other client"}})
    assert s.stop_reason and s.stop_reason.startswith("taken_over")


def test_ledger_usable_from_worker_threads():
    """Regression: sqlite objects must be usable off the thread that created them."""
    s, sent = make()
    t = threading.Thread(target=lambda: s.on_frame(msg("@scribe remember: a thing")))
    t.start()
    t.join()
    assert sent and sent[0][1].startswith("Noted as #1")


def test_ws_url_scheme_follows_base():
    assert wire.ws_url("https://x.example", "a1", "c1").startswith("wss://x.example/agents/a1/connection/ws")
    assert wire.ws_url("http://localhost:8080", "a1", "c1").startswith("ws://localhost:8080/agents/a1/connection/ws")


def test_ws_url_covers_all_rooms_and_resumes():
    """Regression: a single-scope connection that claims no room delivers nothing."""
    url = wire.ws_url("http://h", "a1", "c1", start_from=40, expected_generation=3)
    assert "connection_id=c1" in url and "scope=all" in url and "filter=addressed" in url
    assert "start_from=40" in url and "expected_generation=3" in url
