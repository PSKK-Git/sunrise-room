# 60-second video: Sunrise Room

Record one long take in the `sunrise-demo` room, then cut to the beats below. Only the steps marked PROVEN have run in the real room; mark the rest "try" and cut them if they fail.

Before every take: `cd ~/Desktop/CODE/Hackathons/the_switch && ./scripts/reset_demo.sh`, then ask Claude to restart the scribe (the reset deletes its database). Check Mattermost is healthy.

| Time | On screen | You say / caption |
|---|---|---|
| 0:00-0:05 | Black card, big white text: **"The owner is at a wedding. A washer just ate a customer's bedsheets."** | (silent, text only: it plays with sound off) |
| 0:05-0:18 | Room. Type: `@triager Ravi here: washer 3 stopped mid-cycle with a customer's bedsheets inside. Run shopctl machine 3 and tell me the status and error code, then ask @scribe if we've seen this before.` Show the reply: **E21**, order **O5001**. PROVEN | "Staff post in the room. An agent looks it up in the shop's back office." |
| 0:18-0:28 | Scribe's recall appears: `#2 fix ... (by Ravi)` and `#1 observation ... E21 ... (by Ravi)`. Zoom on "by Ravi". PROVEN | "A memory agent I built answers: we've seen this, and here is who said it." |
| 0:28-0:40 | Type: `@fixer Washer 3 faulted with Anita's order O5001. Stage a refund for Owner to approve. Do not apply it.` Show "waiting for Owner". TRY (not yet run live) | "Agents can prepare a refund. They cannot spend money." |
| 0:40-0:46 | Type as Owner: `approve`. Show it applied. TRY | "Only the owner approves." |
| 0:46-0:56 | Type: `@scribe replace #4: when a machine faults mid-cycle, stage a refund straight away for regulars (Owner still approves it)` then `@scribe blast #3`. Show "#4 is now replaced by #7 (the old one stays on record)" and the list. PROVEN locally, run it in the room once before recording | "Rules change. Nothing is erased. And I can see what rested on the old rule." |
| 0:56-1:00 | End card: **Sunrise Room** / github.com/PSKK-Git/sunrise-room / "Built on Switch" | "Real room. Mock shop. Link below." |

## Editing notes (hook first, no dead air)
- Open on the text card, not a logo. Sound off should still make sense, so burn in captions.
- Cut every wait for an agent. Speed up any wait you must keep to 3x and drop a small "3x" label in the corner.
- Zoom in on the line that matters (E21, "by Ravi", "waiting for Owner"). Everything else stays small.
- Make the Console text bigger with Cmd-plus before recording so it reads on a phone.
- If the fixer and approval steps fail, drop them. The cut still tells the story: report, lookup, memory, rule change. Say honestly in the README what was and wasn't shown live.

## What is real and what is not (say this in the post or the README)
The shop data is invented, and approving changes a JSON file. No money moves. The memory starts with six seeded "earlier weeks" entries.
