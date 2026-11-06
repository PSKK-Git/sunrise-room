# Demo script (target 2:30)

Record in Mattermost (bundled) or Telegram. Run `./scripts/reset_demo.sh` first. Keep the room on screen the whole time; show the terminal only for one second at the end.

**0:00 The problem (15s, voice over the room)**
"A laundromat. Two staff, one owner who's not always there. A washer just died with a customer's clothes inside."

**0:15 Incident one (45s)**
Ravi: `Washer 3 stopped mid-cycle, Anita Rao's bedsheets are inside, she's waiting.`
- Triager restates and hands to fixer.
- Fixer asks `@scribe have we seen washer 3 error E21 before #machine-3`. The scribe answers with entries #1 and #2, naming Ravi as the source.
- Fixer stages: repair for machine 3, and a free re-wash because Anita is a regular, per rule #6.
- Room: "2 things are waiting for Owner."

**1:00 The human gate (25s)**
- Ravi types `approve`. The room answers that only Owner can approve.
- Owner approves the repair and the re-wash. Show the room confirming.
- Fixer tells the scribe: `remember: ... fixed by technician visit, E21 came back same day #machine-3 !fix ^2`.

**1:25 The rule changes (25s)**
Owner: `@scribe replace #4: when a machine faults mid-cycle, stage a refund straight away for regulars (Owner still approves it)`
- Scribe: "#4 is now replaced by #8 (old one stays on record)". (#7 is the fix noted in the previous step. If you skip that step, it is #7.)
- Why the wording: rule #3 (every refund needs Owner approval) stays in force, so the new rule speeds up *staging*, it does not bypass the gate.
- Owner: `@scribe blast #3`. Scribe lists what to re-check.

**1:50 Incident two, later (30s)**
Meena: `Washer 3 is showing E21 again, new customer Vikram.`
- This time the fixer cites the entry from incident one and the **new** rule, not the old one, and goes straight to calling the technician.
- Optional: swap the agent behind `@fixer` (drop the job, another agent takes it) and show the answer is the same because the memory lives in the room, not the agent.

**2:20 Close (10s)**
"Switch gave us the room, the jobs and the owner's gate. The scribe is our own agent on Switch's protocol. Repo and README below."

## Checklist before recording
- [ ] Reset ran, memory shows 6 entries (`@scribe rules`)
- [ ] Ravi really is refused when he tries to approve
- [ ] Screen shows who said what (names visible)
- [ ] README states the seeded history and the mock data
- [ ] Wispr scorecard screenshot saved for the submission
