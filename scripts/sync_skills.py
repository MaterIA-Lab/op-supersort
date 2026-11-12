#!/usr/bin/env python3
"""Mirror .agents/skills/ (source of truth, read by Codex) into .claude/skills/ (read by Claude Code).

Usage:
    python scripts/sync_skills.py           # copy skills
    python scripts/sync_skills.py --check   # exit 1 if .claude/skills is out of date
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".agents" / "skills"
DST = ROOT / ".claude" / "skills"
KEEP = {".gitkeep"}


def in_sync() -> bool:
    def same(a: Path, b: Path) -> bool:
        cmp = filecmp.dircmp(a, b, ignore=list(KEEP))
        if cmp.left_only or cmp.right_only or cmp.funny_files:
            return False
        _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
        if mismatch or errors:
            return False
        return all(same(a / d, b / d) for d in cmp.common_dirs)

    return same(SRC, DST)


def sync() -> None:
    for item in DST.iterdir():
        if item.name in KEEP:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()
    for item in SRC.iterdir():
        if item.name in KEEP:
            continue
        target = DST / item.name
        shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    SRC.mkdir(parents=True, exist_ok=True)
    DST.mkdir(parents=True, exist_ok=True)

    if args.check:
        if not in_sync():
            sys.exit(".claude/skills is out of date. Run: python scripts/sync_skills.py")
        print("Skills are in sync.")
        return

    sync()
    print(f"Synced {SRC.relative_to(ROOT)} -> {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
