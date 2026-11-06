"""Runs the real scribe.agent.run() loop against a local fake Switch server.

The fake speaks the protocol as documented ("Agent connection", "Agent events"): connection_state first,
pings, an addressed message, then an `evicted`/taken_over frame. It checks what the client sends back.
This is still not a live Switch server, but it exercises the socket, auth, URL and reply code paths.
"""
import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest
from websockets.asyncio.server import serve

from scribe import agent


class FakeHttpClient:
    posts: list = []

    def __init__(self, *a, **k):
        pass

    def post(self, url, json=None, headers=None):
        FakeHttpClient.posts.append((url, json, headers))

        class R:
            status_code = 200
            text = ""

        return R()


def message_frame(body, seq):
    return {
        "event": "message",
        "data": {
            "type": "message", "room_id": "room-1", "bridge_id": None, "channel_type": None, "sequence": seq,
            "payload": {"addressed": True, "sender": "@switch-user-x:srv", "sender_name": "Ravi",
                        "message_id": "m-1", "body": body, "timestamp": 1, "thread_id": None, "attachments": []},
        },
        "id": seq,
    }


def test_scribe_runs_against_a_fake_switch(tmp_path, monkeypatch):
    seen = {}
    FakeHttpClient.posts = []

    async def handler(ws):
        seen["auth"] = ws.request.headers.get("Authorization")
        seen["path"] = ws.request.path
        await ws.send(json.dumps({"event": "connection_state",
                                  "data": {"connection_id": "c", "generation": 4, "rooms": ["room-1"], "cursor": 2}}))
        await ws.send(json.dumps({"event": "ping"}))
        seen["pong1"] = json.loads(await ws.recv())
        await ws.send(json.dumps(message_frame("@scribe remember: CleanCo delivers Tuesday #stock", 5)))
        for _ in range(100):  # wait for the reply to be posted
            if FakeHttpClient.posts:
                break
            await asyncio.sleep(0.05)
        await ws.send(json.dumps({"event": "ping"}))
        seen["pong2"] = json.loads(await ws.recv())
        await ws.send(json.dumps({"event": "evicted", "data": {"code": "taken_over", "reason": "test"}}))
        await asyncio.sleep(1)

    async def main():
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            monkeypatch.setenv("SWITCH_URL", f"http://127.0.0.1:{port}")
            await asyncio.wait_for(agent.run(), timeout=15)

    state = tmp_path / "state.json"
    state.write_text(json.dumps({"agent_id": "a1", "api_key": "k-secret", "connection_id": "cid-1"}))
    monkeypatch.setattr(agent, "STATE_FILE", state)
    monkeypatch.setenv("SCRIBE_DB", str(tmp_path / "memory.db"))
    import httpx
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)

    with pytest.raises(SystemExit) as stop:
        asyncio.run(main())

    assert "taken_over" in str(stop.value)  # taken_over is final: no reconnect loop
    assert seen["auth"] == "Bearer k-secret"
    q = parse_qs(urlparse(seen["path"]).query)
    assert urlparse(seen["path"]).path == "/agents/a1/connection/ws"
    assert q["connection_id"] == ["cid-1"] and q["scope"] == ["all"] and q["filter"] == ["addressed"]
    assert seen["pong1"] == {"type": "pong", "cursor": 2}   # from connection_state
    assert seen["pong2"] == {"type": "pong", "cursor": 5}   # after processing sequence 5
    url, body, headers = FakeHttpClient.posts[0]
    assert url.endswith("/agents/a1/message") and headers["Authorization"] == "Bearer k-secret"
    assert body["room_id"] == "room-1" and body["content"].startswith("Noted as #1")
