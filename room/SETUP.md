# Setting up the room (about 30 minutes)

Do these in order. Anything marked CHECK is something I could not verify from the public docs, so test it before building on it.

1. **Switch Console + Docker.** Install Console, let it start the local server, then talk to switch-buddy (the quickstart). Mattermost is bundled, so you need no Slack admin.
2. **Make the room.** Use `room/template.yaml` (replace `{team}`, `{provider}`, `{bridge}`), or ask switch-buddy to create a room called `sunrise` with three agents.
3. **Paste the room instructions.** Console, open the room, Configuration, Instructions: paste `room/instructions.md`.
4. **Define the jobs.** In the room, ask an agent: "define a shared job called triager, a shared job called reviewer and an exclusive job called fixer, using the job descriptions in the room instructions." Job names cannot contain spaces. Check with `!roles`.
5. **Make the shop tools reachable.** The agents run `python -m shop.shopctl` from this repo, so start their sessions with this repo as the working folder. CHECK: where Switch Console runs an agent's commands (your laptop folder vs. inside Docker).
6. **Register the scribe.** Gateway, API Keys, create a key of type *registration*. Then:
   ```
   export SWITCH_URL=http://localhost:<server port>      # the address Console shows as "Server address"
   export SWITCH_REG_KEY=<registration key>
   python -m scribe.agent register
   python -m scribe.agent run
   ```
   Test `curl $SWITCH_URL/health` first. The frame names in `scribe/wire.py` now match the docs pages "Agent connection" and "Agent events". If the socket connects but nothing happens, check that the scribe is a member of the room (step 7) and that the agent's addressing is `anyone`. Close codes 4401 (bad key) and 4409 (taken over or room already claimed) stop the scribe on purpose: do not run two copies with the same connection id.
   Not verified from the docs: the exact shape of `ping`, `connection_state` and `evicted` frames (the code accepts fields at the top level or under `data`), and the template YAML keys in step 2 (see the template language in the Switch repo, `docs/TEMPLATES.md`).
7. **Invite the scribe** into the room: `!invite-agent @scribe`. Then `@scribe help`.
8. **Approval rule.** The agent that applies approvals must only take orders from Owner. Agent settings, "who may address it": admit only Owner (and the other agents) for `fixer`. CHECK: that a message from Ravi really is refused.
9. **Telegram (optional, for the real-world story).** Connect a Telegram bridge using the docs' messaging-apps page and invite Ravi, Meena and Owner. Everything else is unchanged.

## If the scribe cannot connect in time
`python -m scribe.cli` runs the same memory from a terminal. Fallback for the demo: post its answers in the room by hand, and say so in the README. Do not hide it.
