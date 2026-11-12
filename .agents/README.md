# .agents/

The agent toolkit for this project: everything needed to reproduce how the agents were driven.

- `skills/<name>/SKILL.md`: skills, read by Codex from here. Run `python scripts/sync_skills.py` to copy them to `.claude/skills/` for Claude Code.
- `prompts/`: reusable prompts.
- `models.md`: models, settings and providers used, with dates.

MCP servers are configured in `.mcp.json` (Claude Code) and `.codex/config.toml` (Codex).
