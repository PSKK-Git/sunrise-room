# Sunrise Room: a laundromat where people and AI agents run the shop together

*Flip the Switch hackathon entry. Track 1 (Best Business Workflow); also eligible for Best Blog.*

A small laundromat has two staff and an owner who is not always at the counter. When a washer dies with a customer's clothes inside, three things have to happen fast: someone works out what is wrong, someone decides whether to refund, and someone remembers what happened last time. Today that lives in WhatsApp threads and in the owner's head.

Sunrise Room puts all of it in one Switch room. Staff post in chat, AI agents investigate, **nothing that costs money happens until the owner approves**, and a memory agent, the **scribe**, remembers every decision so the next incident starts from what the shop already knows.

## Why this needs Switch

| Switch feature | What we use it for |
|---|---|
| Room + shared history | Staff, owner and agents see the same incident from the first message |
| Room instructions | Every agent that joins gets the shop's rules and tone (`room/instructions.md`) |
| Jobs (roles) | `@triager`, `@fixer` (exclusive, so two agents never refund twice), `@reviewer`. Swap the agent behind a job and the room carries on |
| Addressing rules | Only the owner can instruct the agent that applies approvals |
| Custom agent via the agent protocol | The **scribe** is our own agent, written against Switch's WebSocket/HTTP protocol |
| Telegram / Mattermost bridge | Staff use the chat app they already have |

Take Switch away and there is no shared room, no jobs, no way for the scribe to be addressed by the other agents: the project stops working.

## The scribe (memory)

Every entry records **what** is known, **who** said it (person or agent), **which message**, and **when it was valid**. Nothing is overwritten:

- `replace #4: ...` ends the old rule and links it to the new one; the old one stays on record.
- `blast #3` lists everything built on a rule, so when the owner changes a rule the room sees what to re-check.
- `recall` only returns what is valid now (or at a past time, via the store's `as_of`).

It is a small SQLite store (`scribe/store.py`) with no services to run. The design borrows two ideas from the agent-memory literature: facts that are *invalidated, not deleted* when something changes (Zep/Graphiti), and *provenance on every entry* (Collaborative Memory). We have not benchmarked it and make no accuracy claims; the demo shows the behaviour directly.

## What is real and what is not (read this)

- **Seeded history.** `python -m scribe.seed` loads six entries standing for "earlier weeks". Everything after that is recorded live in the room.
- **Mock shop.** `shop/data.json` is invented. `shopctl` is a command line over it, not a real back office. Approved actions change the file only; no real money moves and no technician is called.
- **Approval is a policy, enforced by Switch.** `shopctl approve --by Owner` takes the approver as an argument, so on its own it can be spoofed by anything that can run the command. The real gate is the room: the agent that runs it only takes instructions from the owner (Switch addressing rules), and the room instructions forbid agents approving on each other's word. We say this plainly rather than call it secure.
- **Scribe wire format.** Checked against Switch's "Agent protocol", "Agent connection" and "Agent events" docs pages (message envelope, `addressed`, `sender_name`/`body`, ping/pong with cursor, resume, `taken_over`). Control-frame shapes beyond the documented fields are accepted at the top level or under `data`. It has now run against a live local Switch server (Switch Console 0.40, server 0.31): the scribe connects, answers staff, and the other agents address it. See "What happened live" below.
- **Tests.** `pytest` (55 tests) covers the memory store, command parsing, the scribe's frame handling and a full connect/ping/reply/stop run against a local fake Switch server and the approval and refund rules. It does not test against a live Switch server.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # 55 tests, no network
./scripts/reset_demo.sh     # restores the shop and seeds the memory
python -m scribe.cli Ravi   # talk to the scribe from a terminal, no Switch needed
python -m shop.shopctl status
```

With Switch: follow `room/SETUP.md` (about 30 minutes).

## Layout

```
scribe/   store.py (ledger) · commands.py (chat commands) · agent.py (Switch client) · wire.py · seed.py · cli.py
shop/     data.json (mock shop) · shopctl.py (lookups, staged actions, owner approval)
room/     instructions.md · template.yaml · SETUP.md
docs/     PLAN.md · DEMO_SCRIPT.md
tests/
```

## Built with

Switch (rooms, jobs, addressing, agent protocol), Claude Code / Codex as the room's agents, Python standard library + `httpx` + `websockets`.

## What happened live

Run in a real Switch room on a local server. **Worked:** the triager read machine 3 through `shopctl` (E21, order O5001); the scribe recalled the earlier entries naming Ravi; the fixer staged a refund (P1, Rs 180) and left it unapplied; the owner approved and it applied, recorded under the owner account; `replace` and `blast` give the right chain (checked on the same memory outside the room). **Not shown live:** a different staff member being refused when they try to approve. In this room there is one account, which Switch treats as the owner. **Things that broke and how they were fixed:** agents ran in an empty folder with no `shopctl`; `python` does not exist on the test machine (only `python3`); the scribe answered plain-English questions from agents with its help text; and the local chat server stalls when the Mac is short of memory. The 60-second video (`docs/sunrise-room-60s.mp4`) is an edited replay of this run: messages are verbatim, long ones shortened. The voiceover is recorded by the author and the background music is generated (no samples, nothing to license). Rebuild with `scripts/make_video.py`, then `scripts/make_audio_from_memo.py <voice-memo>` (needs Pillow and ffmpeg; `scripts/make_audio.py` is a text-to-speech fallback on macOS).
