# A laundromat, three AI agents, and a memory that never overwrites

*Draft for the Flip the Switch hackathon (Best Blog). Fill the bracketed parts after the room has run live.*

A washer dies with a customer's bedsheets inside. The counter staff are standing in front of an annoyed customer. The owner is not there. Three things have to happen: someone works out what is wrong, someone decides whether to refund, and someone remembers what happened the last time.

Today that lives in WhatsApp threads and in the owner's head. I wanted to see whether one Switch room could hold all of it: staff post in chat, AI agents investigate, **nothing that costs money happens until the owner says yes**, and a memory agent remembers every decision so the next incident starts from what the shop already knows.

## What I built

- **A Switch room** for a mock shop, "Sunrise Laundromat", with three jobs: `@triager` (shared), `@fixer` (exclusive, so two agents never refund twice) and `@reviewer` (shared).
- **`shopctl`**, a small command line over an invented back office. Reading is free. Refunds, repairs and reorders can only be *staged*; they run when the owner approves.
- **The scribe**, a custom agent I wrote against Switch's agent protocol. It is a small SQLite ledger with three ideas:
  - every entry records **who** said it and **which message** it came from;
  - nothing is overwritten. `replace #4: ...` ends the old rule and links it to the new one, and the old one stays on record;
  - `blast #3` lists everything built on a rule, so when the owner changes it the room sees what to re-check.

## What surprised me

**The docs were better than my guesses, and my guesses were wrong.** I wrote the first version of the scribe's connection code before I could read the "Agent connection" and "Agent events" pages. When I read them, my code had four problems that would each have stopped it working, and my tests did not catch any of them, because I had written the tests against the same guesses:

1. I looked for `addressed` and the message text one level too high in the frame. The real message is `{"event":"message","data":{"payload":{"addressed", "sender_name", "body"}}}`, so the scribe would have ignored every message.
2. A pong has to carry the highest sequence number you have processed. Pings carry no cursor, so mine would have answered `null` forever.
3. A default connection that claims no room delivers nothing, even though the socket stays open and answers pings. That is a very quiet way to fail.
4. After a `taken_over` eviction you must not reconnect. My retry loop would have fought a second copy of itself.

The fix for the testing problem was to write a fake Switch server that follows the documented protocol and run the real client loop against it. That test now checks the auth header, the URL, the cursor in each pong, the reply post, and the stop on `taken_over`.

**The approval gate is a policy, not a lock.** `shopctl approve --by Owner` takes the approver as an argument, so on its own it can be spoofed by anything that can run the command. The real gate is Switch: the agent that runs it only takes instructions from the owner (addressing rules), and the room instructions forbid agents approving on each other's word. I say so in the README rather than call it secure.

**Refund arithmetic needed a guard.** Two staged refunds on one order could together exceed what the customer paid. `shopctl` now tracks refunded plus waiting money per order.

## What is real and what is not

- The shop data is invented, and approved actions only change a JSON file. No money moves.
- The memory starts with six seeded entries standing for "earlier weeks". Everything after is recorded live.
- 55 tests pass, including the fake-server run. [Replace with: what happened in the live room, once it has run.]
- [Replace with: whether the room's agents could run `shopctl` from the repo folder, and whether Ravi really was refused when he tried to approve. These were the two riskiest assumptions.]

## Try it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
./scripts/reset_demo.sh
python -m scribe.cli Ravi
```

Setup for the room itself is in `room/SETUP.md`.
