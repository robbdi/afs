"""Skill metadata CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import load_config_model
from ..profiles import resolve_active_profile
from ..skills import discover_skills, score_skill_relevance


def skills_list_command(args: argparse.Namespace) -> int:
    config_path = Path(args.config) if args.config else None
    config = load_config_model(config_path=config_path, merge_user=True)
    profile = resolve_active_profile(config, profile_name=args.profile)

    if args.root:
        roots = [Path(path).expanduser().resolve() for path in args.root]
    else:
        roots = list(profile.skill_roots)

    skills = discover_skills(roots, profile=profile.name)
    if args.json:
        payload = {
            "profile": profile.name,
            "roots": [str(path) for path in roots],
            "skills": [
                {
                    "name": skill.name,
                    "path": str(skill.path),
                    "triggers": skill.triggers,
                    "requires": skill.requires,
                    "profiles": skill.profiles,
                }
                for skill in skills
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"profile: {profile.name}")
    if not skills:
        print("(no skills)")
        return 0
    for skill in skills:
        triggers = ",".join(skill.triggers) if skill.triggers else "-"
        requires = ",".join(skill.requires) if skill.requires else "-"
        print(f"{skill.name}\t{skill.path}\ttriggers={triggers}\trequires={requires}")
    return 0


def skills_match_command(args: argparse.Namespace) -> int:
    config_path = Path(args.config) if args.config else None
    config = load_config_model(config_path=config_path, merge_user=True)
    profile = resolve_active_profile(config, profile_name=args.profile)

    if args.root:
        roots = [Path(path).expanduser().resolve() for path in args.root]
    else:
        roots = list(profile.skill_roots)

    skills = discover_skills(roots, profile=profile.name)
    ranked = []
    for skill in skills:
        score = score_skill_relevance(args.prompt, skill)
        if score > 0:
            ranked.append((score, skill))
    ranked.sort(key=lambda item: item[0], reverse=True)

    if args.json:
        payload = {
            "profile": profile.name,
            "prompt": args.prompt,
            "matches": [
                {
                    "score": score,
                    "name": skill.name,
                    "path": str(skill.path),
                    "triggers": skill.triggers,
                    "requires": skill.requires,
                }
                for score, skill in ranked[: args.top_k]
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    for score, skill in ranked[: args.top_k]:
        print(f"{score}\t{skill.name}\t{skill.path}")
    if not ranked:
        print("(no matches)")
    return 0


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("skills", help="Skill metadata and trigger utilities.")
    sub = parser.add_subparsers(dest="skills_command")

    list_parser = sub.add_parser("list", help="List discovered skills.")
    list_parser.add_argument("--config", help="Config path.")
    list_parser.add_argument("--profile", help="Profile name override.")
    list_parser.add_argument("--root", action="append", help="Skill root path override.")
    list_parser.add_argument("--json", action="store_true", help="Output JSON.")
    list_parser.set_defaults(func=skills_list_command)

    match_parser = sub.add_parser("match", help="Rank skill matches for a prompt.")
    match_parser.add_argument("prompt", help="Prompt to score against skill triggers.")
    match_parser.add_argument("--config", help="Config path.")
    match_parser.add_argument("--profile", help="Profile name override.")
    match_parser.add_argument("--root", action="append", help="Skill root path override.")
    match_parser.add_argument("--top-k", type=int, default=10, help="Maximum matches.")
    match_parser.add_argument("--json", action="store_true", help="Output JSON.")
    match_parser.set_defaults(func=skills_match_command)
