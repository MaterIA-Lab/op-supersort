# SuperSort

**Status:** `active` · Part of [OpenPrototypes](https://github.com/MaterIA-Lab/OpenPrototypes)

Search for genuinely new ideas that exploit how a computer works (SIMD, caches, virtual memory, memory bandwidth, multiple cores) to make sorting substantially faster than the best existing implementations.

The project keeps exploring until a relevant finding appears: at least 1.3× faster than the best competitive reference on a practically relevant task, with correct output. A finding of 1.5× or more on an important task is reported to the owner, who decides whether to focus all research on it. Tuning or recombining known sorters does not count. See [GOAL.md](GOAL.md) and the [idea backlog](notes/ideas.md).

## Progress

**Latest result.** Moving unchanged rows directly reached 1.004–1.137× on the 128 MiB synthetic recheck with a cache-buffered reference. It also missed 1.30× in every real flight-duration comparison. The earlier 1.81–2.10× result used the previous reference set. This closes the direct-span line as a research priority. [Follow-up and decision](runs/2026-11-24-key-correction-decision/README.md) · [Original experiment](runs/2026-11-23-key-correction-spans/README.md)

See [PROGRESS.md](PROGRESS.md) for what works and what does not, in plain language. Agents start from [notes/agent-brief.md](notes/agent-brief.md).

## Prior research

SuperSort was researched locally before joining OpenPrototypes. Its lessons, including the negative results, are summarised in [notes/prior-research.md](notes/prior-research.md). The full archive is kept in the git history and is not a constraint on the current work.

## Explore

- [Progress](PROGRESS.md), [research goal](GOAL.md), [notes](notes/) and [iteration logs](runs/)
- [Experimental prototypes](prototypes/agents/) and [usable prototypes](prototypes/humans/)
- [Final summary](SUMMARY.md)

`lab/` is a Git-ignored local workspace for research files and experiments. It is not shared or backed up by Git; meaningful findings and evidence are also recorded in the tracked project.

## Funding

The project starts with personal funding and welcomes cofunding. Spending is reported after experiments or at checkpoints, rather than continuously.

## License

Project contributions are intended to be MIT licensed. Third-party materials retain their own licenses and attribution; review their inclusion before publication.
