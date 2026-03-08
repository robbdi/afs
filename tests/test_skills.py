from __future__ import annotations

from pathlib import Path

from afs.skills import discover_skills, parse_skill_metadata, score_skill_relevance


def test_parse_skill_frontmatter() -> None:
    path = Path(__file__).parent / "fixtures" / "skill_frontmatter" / "SKILL.md"
    metadata = parse_skill_metadata(path)

    assert metadata.name == "gemini-work"
    assert metadata.triggers == ["gemini-cli", "agent studio"]
    assert metadata.requires == ["knowledge/work", "gemini mcp"]
    assert metadata.profiles == ["work", "general"]


def test_discover_skills_profile_filter(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    work_skill = root / "work" / "SKILL.md"
    zelda_skill = root / "zelda" / "SKILL.md"
    work_skill.parent.mkdir(parents=True)
    zelda_skill.parent.mkdir(parents=True)

    work_skill.write_text(
        "---\n"
        "name: work-skill\n"
        "triggers: [gemini]\n"
        "profiles: [work]\n"
        "---\n",
        encoding="utf-8",
    )
    zelda_skill.write_text(
        "---\n"
        "name: zelda-skill\n"
        "triggers: [alttp]\n"
        "profiles: [zelda]\n"
        "---\n",
        encoding="utf-8",
    )

    work_only = discover_skills([root], profile="work")
    assert [skill.name for skill in work_only] == ["work-skill"]


def test_score_skill_relevance() -> None:
    path = Path(__file__).parent / "fixtures" / "skill_frontmatter" / "SKILL.md"
    metadata = parse_skill_metadata(path)
    score = score_skill_relevance("Need gemini-cli setup for agent studio", metadata)
    assert score >= 1
