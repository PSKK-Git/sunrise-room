# Plan (deadline: Sat 7 Nov, 11:59 PM IST; target submit 6 PM)

Times are IST. Today is Fri 6 Nov.

## Today (Fri) - get the room working
- [ ] Register for the hackathon, star the Switch repo, join the WeMakeDevs Discord
- [ ] Install Switch Console + Docker, finish the quickstart (agent answers in Mattermost)
- [ ] Follow `room/SETUP.md` steps 2-4: room, instructions, jobs
- [ ] **Test the two risky things first** (they decide the demo):
  1. Can a room's Claude Code agent run `python -m shop.shopctl` from this repo?
  2. When Ravi tries to approve, is he really refused by the fixer's addressing rules?
- [ ] Run one end-to-end incident with no scribe: report -> triage -> stage -> owner approves

## Tonight - the scribe
- [ ] `register` + `run`; compare `scribe/wire.py` with docs pages "Agent connection" and "Agent events"; fix any names
- [ ] `@scribe help` works in the room
- [ ] **Go / no-go at about 1 AM**: if the scribe cannot talk to the room, fall back to `scribe.cli` + a ledger file attached as a reference, and say so in the README

## Sat morning - make it good
- [ ] Incident two uses the memory (cites #1/#2 and the replaced rule)
- [ ] Agent swap behind `@fixer`
- [ ] Rehearse `docs/DEMO_SCRIPT.md` twice
- [ ] **Feature freeze at 12:00**

## Sat afternoon - ship
- [ ] Record demo (2-3 min), re-record once if a name or a rule is wrong on screen
- [ ] README: fill the "Built with" line honestly; keep the "what is real and what is not" section
- [ ] Blog post (Best Blog): what we built, how we set up Switch, what surprised us
- [ ] #HowISwitch post with the demo clip
- [ ] Wispr: dictate the README or blog and save the Insights screenshot
- [ ] **Submit by 6 PM IST** (repo + demo video + README), then leave buffer

## Cut list if time runs out (cut from the top)
1. Telegram bridge (stay on Mattermost)
2. Agent swap in the demo
3. `blast` and `history` in the demo (keep `replace`)
4. Blog

## Rules to remember
- Existing code/libraries are fine, but the Switch setup and workflow must be built during Nov 4-7
- At most 18+ individuals; one account; AI tools allowed but you must be able to explain what you submit
- Core-contribution prize needs an assigned issue; skip it unless there is spare time
