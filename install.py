"""Copy the Upwork skill into Cursor, Codex, and Claude skill folders."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "skills" / "upwork-agent" / "SKILL.md"
HOMES = (
    Path.home() / ".cursor" / "skills" / "upwork-agent",
    Path.home() / ".codex" / "skills" / "upwork-agent",
    Path.home() / ".claude" / "skills" / "upwork-agent",
)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"missing skill: {SOURCE}")
    for dest in HOMES:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, dest / "SKILL.md")
        print(dest / "SKILL.md")


if __name__ == "__main__":
    main()
