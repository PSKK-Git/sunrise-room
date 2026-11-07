# The washing machine ate a customer's bedsheets, and the owner was at a wedding

*Flip the Switch hackathon · Sunrise Room*

A washer in a small laundromat dies with a customer's bedsheets inside. Meena, at the counter, needs two answers: is this machine known to be faulty, and may I refund this? The owner is at a wedding. So she types into WhatsApp and hopes.

I put the whole scene in one Switch room. Staff post like it's a group chat. Three agents do the legwork: one diagnoses the fault, one prepares the refund, one checks the plan. One rule sits above everything: **nothing that costs money happens until the owner says yes.**

The part I built is the **scribe**, a memory agent that never erases. When a rule changes, the old one is superseded and kept, so you can still explain last Tuesday's refund. `blast #3` shows what else rested on a rule before you change it. (The idea comes from Zep's Graphiti. Mine is one SQLite file, and I haven't benchmarked it.)

In a real room, the triager read the machine's fault (E21), the scribe recalled the earlier incident and named who reported it, and the fixer staged a Rs 180 refund that waited for my approval. It also broke in ways 55 passing tests never caught: agents in an empty folder, no `python` on the machine, and a chat server that stalled when the laptop ran low on memory.

**Honest limits:** the shop is a mock and no money moves. Approval is a policy enforced by Switch's addressing rules, not a lock. And I couldn't show a second staff member being refused, because the room had one account.

Without Switch's rooms, jobs, addressing and protocol, this is a script on my laptop. With them, the scribe is a teammate.

Code and demo: https://github.com/PSKK-Git/sunrise-room
