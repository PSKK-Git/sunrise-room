"""The scribe: a custom Switch agent that keeps the shop's memory.

Run:
    python -m scribe.agent register     # once; needs SWITCH_URL and SWITCH_REG_KEY
    python -m scribe.agent run          # connects and answers when addressed

The decision logic (`Scribe.on_frame`) has no network code so it is unit tested.
The wire names are verified against the Switch docs and live in wire.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Callable, Optional

from . import wire
from .commands import handle
from .store import Ledger

# Close codes after which retrying cannot help (bad key, bad query, room refused, taken over).
FATAL_CLOSE_CODES = {4400, 4401, 4403, 4409}
CONTROL_TYPES = wire.TYPE_CONNECTION_STATE + wire.TYPE_EVICTED + wire.TYPE_REFUSED + wire.TYPE_GAP


class Scribe:
    def __init__(self, ledger: Ledger, post: Callable[..., None], bot_names=("scribe",), self_names=("scribe",)):
        self.ledger = ledger
        self.post = post
        self.bot_names = tuple(bot_names)
        self.self_names = {n.lower() for n in self_names}
        self.cursor: Optional[int] = None      # highest sequence processed
        self.generation: Optional[int] = None
        self.rooms: list[str] = []
        self.stop_reason: Optional[str] = None  # set when the server says do not reconnect
        self._lock = threading.Lock()

    def _advance(self, seq: Optional[int]) -> None:
        if seq is not None and (self.cursor is None or seq > self.cursor):
            self.cursor = seq

    def on_frame(self, frame: dict) -> Optional[dict]:
        """Handle one incoming frame. Returns a frame to send back (a pong) or None."""
        kind = wire.frame_type(frame)
        if kind in wire.TYPE_PING:
            return wire.pong(self.cursor)
        body = wire.frame_body(frame)
        if kind in wire.TYPE_CONNECTION_STATE:
            self.cursor = body.get("cursor", self.cursor)
            self.generation = body.get("generation", self.generation)
            self.rooms = list(body.get("rooms", self.rooms) or [])
            return None
        if kind in wire.TYPE_GAP:
            self.cursor = body.get("resumed_at", self.cursor)
            return None
        if kind in wire.TYPE_EVICTED:
            code = str(body.get("code", ""))
            # taken_over is final; closed may be permanent (agent deleted). Others: reopen and resume.
            if code in ("taken_over", "closed"):
                self.stop_reason = f"{code}: {body.get('reason', '')}"
            return None
        if kind in wire.TYPE_REFUSED:
            self.stop_reason = f"refused {body.get('status')}: {body.get('detail')}"
            return None

        seq = wire.frame_sequence(frame)
        msg = wire.parse_message(frame)
        if msg is not None and msg.sender.lower() not in self.self_names:  # never answer ourselves
            with self._lock:  # the ledger is shared between worker threads
                reply = handle(self.ledger, msg.sender, msg.content, msg_id=msg.message_id, bot_names=self.bot_names)
            if reply:  # empty means "not for me": say nothing
                self.post(msg.room_id, reply)
        self._advance(seq)
        return None


# ----------------------------------------------------------------- networking
STATE_FILE = Path(os.environ.get("SCRIBE_STATE", ".scribe_state.json"))


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))
    try:
        STATE_FILE.chmod(0o600)  # it holds the agent's API key
    except OSError:
        pass


def register() -> None:
    import httpx

    base = os.environ["SWITCH_URL"].rstrip("/")
    key = os.environ["SWITCH_REG_KEY"]
    state = _load_state()
    if state.get("agent_id"):
        print("Already registered as", state["agent_id"], "- delete", STATE_FILE, "to start over.")
        return
    body = wire.registration_body("scribe", "Keeps the laundromat's memory: decisions, rules, past incidents.")
    r = httpx.post(f"{base}/agents", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    state.update(agent_id=data["id"], api_key=data["api_key"], connection_id=str(uuid.uuid4()))
    _save_state(state)  # save before the next call: the key is shown only once
    # A new agent answers only its owner. Older servers let the agent widen that itself; newer ones answer 403
    # ("an agent can't change its own settings"), and the owner must do it in Switch Console instead.
    r = httpx.post(
        f"{base}/agents/{state['agent_id']}/ops/update_agent_detail",
        json={"agent_id": state["agent_id"], "addressing": "anyone"},
        headers={"Authorization": f"Bearer {state['api_key']}"},
        timeout=30,
    )
    print("Registered scribe as", state["agent_id"])
    if r.status_code == 403:
        print("Next: in Switch Console open Your Agents > scribe and set who can instruct it (anyone / the room).")
    else:
        r.raise_for_status()


async def run() -> None:
    import httpx
    import websockets

    base = os.environ["SWITCH_URL"].rstrip("/")
    state = _load_state()
    if not state.get("agent_id"):
        sys.exit("Not registered yet. Run: python -m scribe.agent register")
    headers = {"Authorization": f"Bearer {state['api_key']}"}
    ledger = Ledger(os.environ.get("SCRIBE_DB", "memory.db"))
    client = httpx.Client(timeout=30)

    def post(room_id: str, content: str) -> None:
        try:
            r = client.post(
                f"{base}/agents/{state['agent_id']}/message",
                json={"room_id": room_id, "content": content},
                headers=headers,
            )
            if r.status_code >= 400:
                print("post failed:", r.status_code, r.text[:200], file=sys.stderr)
        except httpx.HTTPError as e:
            print("post failed:", e, file=sys.stderr)

    scribe = Scribe(ledger, post)
    backoff = 1
    while True:
        url = wire.ws_url(
            base,
            state["agent_id"],
            state["connection_id"],
            start_from=scribe.cursor,
            expected_generation=scribe.generation,
        )
        queue: asyncio.Queue = asyncio.Queue()

        async def worker() -> None:
            # Messages are handled here, in order, so a slow reply never delays a pong.
            while True:
                frame = await queue.get()
                try:
                    await asyncio.to_thread(scribe.on_frame, frame)
                except Exception as e:  # one bad message must not kill the scribe
                    print("error handling frame:", e, file=sys.stderr)

        w = asyncio.create_task(worker())
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                backoff = 1
                async for raw in ws:
                    frame = json.loads(raw)
                    kind = wire.frame_type(frame)
                    if kind in wire.TYPE_PING:
                        await ws.send(json.dumps(scribe.on_frame(frame)))  # answer first, always
                    elif kind in CONTROL_TYPES:
                        scribe.on_frame(frame)  # cheap: apply now
                    else:
                        queue.put_nowait(frame)
                    if scribe.stop_reason:
                        sys.exit(f"Server says do not reconnect ({scribe.stop_reason}).")
        except websockets.exceptions.ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            if code in FATAL_CLOSE_CODES:
                sys.exit(f"Server closed the connection with {code} ({e.rcvd.reason}). Not retrying.")
            print("connection closed:", code, "- retrying in", backoff, "s", file=sys.stderr)
        except OSError as e:
            print("connection lost:", e, "- retrying in", backoff, "s", file=sys.stderr)
        finally:
            w.cancel()
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "register":
        register()
    elif cmd == "run":
        asyncio.run(run())
    else:
        sys.exit("usage: python -m scribe.agent [register|run]")
