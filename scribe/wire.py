"""Everything about the Switch wire format lives in this one file.

Verified against the Switch docs pages "The agent protocol", "Agent connection" and
"Agent events" (docs.switchagents.ai, switch-rooms/internals):

  * register once:   POST {base}/agents  (registration key as bearer)
        body: name (^[a-z0-9][a-z0-9._-]*$), description, connector_type, integration_profile
        response: {id, api_key}  (the key is shown once)
  * connect:         WebSocket {base}/agents/{agent_id}/connection/ws
        bearer = the agent's API key; query: connection_id (UUID, reused across reconnects),
        scope=all|single, filter=all|addressed, rooms=<ids>, start_from, expected_generation
        NOTE: a default single-scope connection that claims no room delivers NOTHING,
        so we use scope=all.
  * first frame is `connection_state` (rooms, cursor, generation). Keep generation.
  * the server pings every 2s; answer at once with {"type": "pong", "cursor": <highest sequence>}.
    No answer for 6s evicts the connection.
  * domain events arrive as
        {"event": "message", "data": {"type", "room_id", "bridge_id", "channel_type",
                                      "payload": {...}, "sequence": N}, "id": N}
    message payload: addressed, sender, sender_name, message_id, body, timestamp, thread_id, attachments
  * act on a message only when payload.addressed is true
  * post a message:  POST {base}/agents/{agent_id}/message  {room_id, content}  (no connection needed)
  * who may talk to the agent: POST .../ops/update_agent_detail {agent_id, addressing}
        (own API key, no connection needed); addressing = owner_only | owner_and_owner_agents | anyone
  * evicted frame codes: taken_over = STOP (never reconnect); heartbeat_lapsed etc = reopen and resume
  * close codes: 4401 bad key, 4409 taken over / refused, 4400 bad query
  * GET {base}/health is the public probe for "is this the right base URL"

Not verified: the exact shape of control frames (`ping`, `connection_state`, `evicted`) beyond the
fields listed in the docs. We accept the fields either at the top level or under `data`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

FRAME_TYPE_KEYS = ("event", "type", "kind")
TYPE_CONNECTION_STATE = ("connection_state",)
TYPE_PING = ("ping",)
TYPE_EVICTED = ("evicted",)
TYPE_REFUSED = ("refused",)
TYPE_GAP = ("gap",)
TYPE_PONG = "pong"
TYPE_MESSAGE = ("message",)


def _first(d: dict, keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def frame_type(frame: dict) -> str:
    return str(_first(frame, FRAME_TYPE_KEYS, "")).lower()


def frame_body(frame: dict) -> dict:
    """Control-frame fields may sit at the top level or under `data`."""
    data = frame.get("data")
    return data if isinstance(data, dict) else frame


def frame_sequence(frame: dict) -> Optional[int]:
    """Sequence number of a domain event (same number as `id`), else None."""
    data = frame.get("data")
    for src in (data if isinstance(data, dict) else {}, frame):
        for k in ("sequence", "id"):
            v = src.get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                return v
            if isinstance(v, str) and v.isdigit():
                return int(v)
    return None


def ws_url(
    base: str,
    agent_id: str,
    connection_id: str,
    rooms: list[str] | None = None,
    start_from: int | None = None,
    expected_generation: int | None = None,
) -> str:
    scheme = "wss" if base.startswith("https") else "ws"
    host = base.split("://", 1)[-1].rstrip("/")
    q: dict[str, Any] = {"connection_id": connection_id, "scope": "all", "filter": "addressed"}
    if rooms:
        q["rooms"] = ",".join(rooms)
    if start_from is not None:
        q["start_from"] = start_from
    if expected_generation is not None:
        q["expected_generation"] = expected_generation
    return f"{scheme}://{host}/agents/{agent_id}/connection/ws?{urlencode(q, safe=',')}"


def registration_body(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "connector_type": "custom-python",
        "integration_profile": {
            "connection_model": "session_addressable",
            "message_exchange": True,
            "pre_invocation_mediation": [],
            "post_invocation_mediation": [],
            "event_reporting": [],
        },
    }


@dataclass
class Incoming:
    room_id: str
    sender: str       # display name (sender_name); participant ids are opaque
    sender_id: str
    content: str
    message_id: str
    thread_id: Optional[str] = None


def parse_message(frame: dict) -> Optional[Incoming]:
    """Return the message if this frame is a message addressed to us, else None."""
    if frame_type(frame) not in TYPE_MESSAGE:
        return None
    data = frame_body(frame)
    payload = data.get("payload")
    if not isinstance(payload, dict) or payload.get("addressed") is not True:
        return None
    sender_id = str(payload.get("sender") or "")
    sender = str(payload.get("sender_name") or sender_id or "someone")
    return Incoming(
        room_id=str(data.get("room_id") or payload.get("room_id") or ""),
        sender=sender,
        sender_id=sender_id,
        content=str(payload.get("body") or ""),
        message_id=str(payload.get("message_id") or ""),
        thread_id=payload.get("thread_id"),
    )


def pong(cursor: Any) -> dict:
    return {"type": TYPE_PONG, "cursor": cursor}
