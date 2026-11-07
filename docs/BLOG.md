# The washing machine ate a customer's bedsheets, and the owner was at a wedding

*Flip the Switch hackathon, Best Blog entry. Project: Sunrise Room.*

It is 4:40 on a Saturday. A washer in a small laundromat has died with somebody's bedsheets inside. The customer is standing at the counter, polite and getting less polite. The counter staff, Meena, has two questions she cannot answer: *is this machine known to be dodgy?* and *am I allowed to refund this?*

The owner is at a cousin's wedding. So Meena does what every small shop does. She types into WhatsApp, waits, and hopes.

I have watched this exact scene in shops my family goes to. Nothing in it is hard. What is missing is one place where the people, the facts and the permission all sit together. And, quietly, a memory. Somebody refunded this same customer last month. Somebody decided regulars get a refund straight away. That "somebody" is usually the owner's head.

So for this hackathon I tried to put the whole thing in one Switch room.

## What it does

Staff post in the room like they would in a group chat. Three AI agents take the jobs nobody has time for:

- **`@triager`** works out what is wrong and whether it has happened before.
- **`@fixer`** prepares the refund, the repair call or the reorder. It is an *exclusive* job, so two agents can never both refund the same person.
- **`@reviewer`** checks the plan before it goes to the owner.

One rule sits above all of it: **nothing that costs money happens until the owner says yes.** The agents stage a refund. They cannot complete it.

And there is a fourth member of the room, the one I actually built: **the scribe**.

## The scribe: a memory that doesn't lie about the past

Most "AI memory" is a pile of notes the model rereads. That breaks the first time a rule changes. Say the shop's rule was "regulars get refunds up to Rs 300", and last week the owner changed it to Rs 200. If you overwrite the note, you can no longer explain why Tuesday's refund was Rs 300. If you keep both, the AI might quote either.

The scribe does what an accountant would do. **It never erases. It supersedes.**

- Every entry records *who* said it and *which message* it came from. If it is wrong, you can see whose word it was.
- `replace #4: ...` ends the old rule on that date and points it at the new one. The old rule stays on record, marked as no longer current.
- `blast #3` answers a question owners actually have: *"If I change this rule, what else did we decide because of it?"* It lists everything built on top.
- Asking "what's true now?" returns only current entries. Asking "what did we believe last Tuesday?" is possible too.

The idea is not mine. The agent-memory research community landed on it independently: Zep's Graphiti marks a fact as invalid when something newer contradicts it, instead of deleting it ([Thoughtworks Radar](https://www.thoughtworks.com/radar/platforms/graphiti), [a summary of the Zep paper](https://signals.aktagon.com/articles/2026/07/zep-a-temporal-knowledge-graph-architecture-for-agent-memory/)). I borrowed the principle and shrank it to one SQLite file, because a laundromat does not run a graph database. I have not benchmarked it against anything and I won't pretend it beats those systems. It is small, it is legible, and you can read the whole ledger with your eyes.

## Where I got it wrong first

I wrote the scribe's connection code before I had read the "Agent connection" and "Agent events" pages. When I finally read them, I found four bugs, each of which would have stopped it working, and **my own tests had passed all four**, because I wrote the tests against the same wrong guesses.

1. I looked for the message text one level too high in the frame. The scribe would have sat in the room ignoring every message.
2. A pong has to carry the highest sequence number you have processed. Mine would have answered `null` forever.
3. A connection that claims no rooms receives nothing, yet the socket stays open and keeps answering pings. A very quiet way to fail.
4. After a `taken_over` eviction you must not reconnect. My retry loop would have fought a second copy of itself.

Lesson: a test written from your own assumptions only proves your assumptions agree with each other. So I built a small fake Switch server that follows the documented protocol, and ran the real client loop against it. It checks the auth header, the URL, the cursor in each pong, the reply, and the stop on `taken_over`.

A second, smaller catch: two staged refunds on one order could together exceed what the customer paid. Money bugs are the kind that make an owner stop trusting a tool, so `shopctl` now counts refunded plus pending per order.

## The honest part

I would rather you trust the three claims I make than be impressed by ten.

- **The shop is pretend.** The data is invented, and "approving" changes a JSON file. No money moves, no technician is called.
- **Approval is a policy, not a lock.** `shopctl approve --by Owner` takes the approver as an argument, so anything that can run the command could lie. The real gate is Switch: the agent that runs it only takes instructions from the owner, and the room's instructions tell agents never to approve on another agent's word. I say this in the README instead of calling it secure.
- **The memory starts with six seeded entries**, standing in for "earlier weeks". Everything after that is recorded live in the room.
- **Tests:** 55 pass, including the fake-server run. [LIVE-ROOM RESULT: replace with what happened in the real room: whether the scribe connected, whether agents could run `shopctl`, and whether Ravi was refused when he tried to approve. Delete this bracket if you cannot report it truthfully.]

## Why Switch, specifically

Take Switch away and this project falls over. There is no shared room where a customer problem lives with its history. There are no jobs, so I could not say "exclusive" and let the platform guarantee one refund. And there is no agent protocol, so the scribe would be a script on my laptop and not a member of the team the other agents can address. The room, the jobs, the addressing rules and the protocol are the product. My code is the shop-specific part on top.

## Try it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # 55 tests, no network
./scripts/reset_demo.sh     # fresh shop and seeded memory
python -m scribe.cli Ravi   # talk to the scribe from a terminal
```

Room setup is in `room/SETUP.md`.

---

*What I'd build next:* a Telegram bridge so Meena never has to open anything new, and an owner digest each evening: "three rules changed today, two decisions rest on them." The memory is the part I'd keep. The agents are replaceable. The shop's own history is the one thing that is not.
