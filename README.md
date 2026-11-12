# SuperSort

**Status:** `active` · Part of [OpenPrototypes](https://github.com/MaterIA-Lab/OpenPrototypes)

Search for genuinely new ideas that exploit how a computer works (SIMD, caches, virtual memory, memory bandwidth, multiple cores) to make sorting substantially faster than the best existing implementations.

The project keeps exploring until a relevant finding appears: at least 1.3× faster than the best competitive reference on a practically relevant task, with correct output. A finding of 1.5× or more on an important task is reported to the owner, who decides whether to focus all research on it. Tuning or recombining known sorters does not count. See [GOAL.md](GOAL.md) and the [idea backlog](notes/ideas.md).

## Progress

**Best result so far:** merging two sorted batches of large records by remapping memory pages instead of copying them was 1.33–1.36× faster than the best merge into a new output on synthetic data, but only when the batches overlap at their edges, and it loses when the caller already has an output buffer. No relevant finding under the goal has been confirmed yet.

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
