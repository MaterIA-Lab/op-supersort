---
name: close-run
description: Close a research iteration in an OpenPrototypes project. Use when an experiment, probe, pilot or setup run has finished (or was abandoned) and its results must be recorded, before pushing. Adds the run's front matter, updates PROGRESS.md for humans and notes/agent-brief.md for agents, and regenerates the run ledger.
---

# Close a run

Use this at the end of every iteration, including failed, inconclusive or abandoned ones. The goal is that a person reading `PROGRESS.md`, or an agent reading `notes/agent-brief.md`, learns what this run changed without opening it.

## 1. Front matter of the run

Open `runs/<YYYY-MM-DD>-<name>/README.md` and make sure it starts with the block described in `runs/README.md`:

- `title`, `date` (add the UTC time `HH:MM` if other runs share the day), `verdict`, `summary`, `model` are required.
- Pick the `verdict` from the table in `runs/README.md`. Be strict: `works` only when the project's success threshold was met on fresh inputs. A measured gain with open caveats is `promising`. A preregistered threshold that was missed is `failed`, even if something interesting was seen.
- `summary`: one or two plain sentences a non-expert can follow. Say what was learned and, for a failure, the cause as far as it is known. Include the key number.
- `result` and `baseline`: the headline number and what it is compared with. Never put a number you did not measure.
- `closes` / `opens`: lines of work this run ends or starts.
- `model` and `cost`: the real model identifier and settings if known, tokens and money if known, otherwise `not captured`. Never guess.
- `speedup` (and `estimate: true` for headroom estimates): the headline ratio, best reference time ÷ candidate time. Omit it when nothing comparable was timed.
- **Website explanation** (required unless the verdict is `setup`): `how`, `compared_with` and `faster_where`, plus the Spanish `title_es`, `how_es`, `compared_with_es` and `faster_where_es`. These appear on the public project page when someone clicks the run, so write them for a curious non-expert: how the idea was supposed to work, what it raced against, and where it was faster or slower and by how much, with the conditions next to each number. Keep the caveats; never round a loss into a win.

## 2. Update the human view: PROGRESS.md

Edit the hand-written sections above the generated table:

- **Where we are**: one short paragraph. Is there a relevant finding yet?
- **What works so far**: only measured gains, each with its conditions and caveats next to the number.
- **What does not work**: each closed line in plain language, with the reason.
- **What comes next**: one to three items.

Write for a curious non-expert: no jargon without a short explanation, no internal run IDs in the text (link them instead). Update the `Last updated` date.

## 3. Update the agent view: notes/agent-brief.md

Edit the curated sections above the generated ledger. Be dense and precise:

- **State of each line of work**: status, best evidence with exact numbers, next step.
- **Do not retry**: anything this run closed, with the measured cause and a link.
- **Controls and references to beat**: add any control that turned out stronger than expected.
- **Contracts used so far** and **Environment and harness notes**: anything the next agent would otherwise rediscover the hard way (setup traps, pinned versions, platform limits).

Update the `Last updated` date. Remove statements that are no longer true instead of piling up history: the history lives in `runs/`.

## 4. Regenerate and check

```sh
python scripts/build_progress.py
python scripts/build_progress.py --check
```

This rewrites `runs/index.json` and the generated tables in both views. CI runs the check on every `agent/*` push and blocks the automatic merge if it fails.

## 5. Escalate when required

If the result meets the project's threshold for reporting to the owner (see `GOAL.md` and `AGENTS.md`), report it as instructed there before continuing broad exploration.
