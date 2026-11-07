# The washing machine ate a customer's bedsheets, and the owner was at a wedding

*Flip the Switch hackathon · Sunrise Room*

It's 4:40 on a Saturday. A washer in a small laundromat dies with a customer's bedsheets inside. Meena, at the counter, needs two answers: is this machine known to be dodgy, and am I allowed to refund this? The owner is at a cousin's wedding. So she does what every small shop does. She types into WhatsApp and hopes.

Nothing in that scene is hard. What's missing is one place where the people, the facts and the permission sit together, plus a memory. So I put all of it in one Switch room.

## What it does

Staff post in the room like a group chat. Three agents do the legwork: `@triager` finds out what's wrong and whether it has happened before, `@fixer` prepares the refund, repair or reorder, and `@reviewer` checks the plan.

One rule sits above all of it: **nothing that costs money happens until the owner says yes.** Agents stage a refund. They can't complete it.

## The scribe: a memory that never erases

The fourth member is the one I built. Most "AI memory" is a pile of notes that breaks the first time a rule changes. The scribe works like an accountant: it supersedes, it never erases.

- Every entry records who said it and in which message.
- `replace #4: ...` ends the old rule and keeps it on record.
- `blast #3` answers the owner's real question: *if I change this rule, what else rested on it?*

The idea isn't new. Zep's Graphiti marks a fact invalid instead of deleting it ([Thoughtworks Radar](https://www.thoughtworks.com/radar/platforms/graphiti)). I shrank it to one SQLite file, and I haven't benchmarked it.

## What actually happened

I ran it in a real room. The triager read machine 3 (error E21). The scribe recalled the earlier incident and named Ravi as the source. The fixer staged a Rs 180 refund that sat there until I approved it.

It also broke in ways 55 passing tests never showed. My agents started in an empty folder with no shop tool. The machine has `python3` but no `python`. The chat server stalled when the laptop ran low on memory. And my first scribe had four protocol bugs that my own tests happily passed, because I'd written the tests from the same wrong guesses. A small fake server that follows the documented protocol fixed that.

## Honest limits

The shop is a mock: approving edits a JSON file and no money moves. Approval is a policy enforced by Switch's addressing rules, not a lock. And I couldn't show a second staff member being refused, because the room had one account, which Switch treats as the owner.

## Why Switch

Without the room, the jobs, the addressing rules and the agent protocol, this is a script on my laptop. With them, the scribe is a teammate the other agents can talk to.

Code, demo and setup: https://github.com/PSKK-Git/sunrise-room
