"""Skill loader: reads SKILL.md files from knowledge/skills/ and returns their content."""

from __future__ import annotations

from pathlib import Path

from core.paths import KNOWLEDGE_DIR


_SKILLS_DIR = KNOWLEDGE_DIR / "skills"

# Maps skill name to directory path under knowledge/skills/
_SKILL_LOCATIONS: dict[str, Path] = {
    "frontend-design": _SKILLS_DIR / "art" / "frontend-design",
    "imagegen":        _SKILLS_DIR / "art" / "imagegen",
}


def load_skill(name: str) -> str | None:
    """Return the content of a SKILL.md file by skill name, or None if not found."""
    location = _SKILL_LOCATIONS.get(name)
    if location is None:
        return None
    skill_file = location / "SKILL.md"
    if not skill_file.exists():
        return None
    return skill_file.read_text(encoding="utf-8")


def write_skill_guidance(out_dir: Path, *skill_names: str) -> None:
    """Write a skill_guidance.md to out_dir containing the content of the requested skills.

    Called during apply_development_plan_outputs so AI agents executing the step
    will find the applicable skill guidelines alongside the stage artifacts.
    """
    sections: list[str] = []
    for name in skill_names:
        content = load_skill(name)
        if content:
            sections.append(f"<!-- skill: {name} -->\n{content}")
    if not sections:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "skill_guidance.md").write_text(
        "# Skill Guidance\n\n" + "\n\n---\n\n".join(sections),
        encoding="utf-8",
    )
