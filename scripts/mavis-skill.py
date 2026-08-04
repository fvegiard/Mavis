#!/usr/bin/env python3
"""
mavis-skill.py — Skill auto-loader / autoselect for Mavis.

The top 1% agents (Claude Code, Manus) auto-load relevant skills based on
the user request. This is Mavis's version:
  - Scans available skills (Claude Code + custom)
  - Ranks by keyword match against user request
  - Returns the top-N skills to load

Usage:
  mavis-skill "build a react dashboard"          # returns top skills
  mavis-skill --load "deploy a docx file"         # actually loads them
  mavis-skill list                                # list all available
  mavis-skill scan                                # rescan skill directories
"""
import argparse
import os
import re
import sys
from pathlib import Path

SKILL_DIRS = [
    Path("/workspace/.skills"),
    Path("/root/.claude/skills"),
    Path("/usr/local/share/claude/skills"),
    Path(os.path.expanduser("~/.claude/skills")),
]


def scan_skills() -> dict:
    """Scan all skill directories and return {name: {path, description, body}}."""
    skills = {}
    for d in SKILL_DIRS:
        if not d.exists():
            continue
        for skill_file in d.rglob("SKILL.md"):
            try:
                content = skill_file.read_text()
            except Exception:
                continue
            # Parse frontmatter
            name = skill_file.parent.name
            description = ""
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                        elif line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
            skills[name] = {
                "path": str(skill_file),
                "dir": str(skill_file.parent),
                "description": description,
                "keywords": extract_keywords(content),
            }
    return skills


def extract_keywords(text: str) -> set:
    """Extract keywords from skill content (lowercase, stop words removed)."""
    stop = {"the", "a", "an", "is", "are", "be", "to", "of", "and", "or", "in", "on", "at", "for", "with", "by"}
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return {w for w in words if w not in stop}


def rank_skills(skills: dict, request: str, top_n: int = 5) -> list:
    """Rank skills by relevance to user request."""
    request_keywords = extract_keywords(request)
    scores = []
    for name, info in skills.items():
        overlap = len(request_keywords & info["keywords"])
        # Boost by description match
        desc_words = extract_keywords(info["description"])
        desc_overlap = len(request_keywords & desc_words) * 2
        total = overlap + desc_overlap
        if total > 0:
            scores.append((total, name, info))
    scores.sort(key=lambda x: -x[0])
    return scores[:top_n]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("request", nargs="?", help="User request to match skills against")
    p.add_argument("--load", action="store_true", help="Load the matched skills (output as prompt injection)")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--list", action="store_true", help="List all available skills")
    p.add_argument("--scan", action="store_true", help="Rescan and cache")

    args = p.parse_args()

    if args.list:
        skills = scan_skills()
        print(f"📚 {len(skills)} skills available")
        for name, info in sorted(skills.items()):
            print(f"   - {name}: {info['description'][:80]}")
        return 0

    if not args.request:
        print("Usage: mavis-skill 'request' [--load] [--top N]", file=sys.stderr)
        return 1

    skills = scan_skills()
    ranked = rank_skills(skills, args.request, args.top)
    if not ranked:
        print("🤷 No relevant skills found for this request.")
        return 0

    if args.load:
        # Output skill contents for prompt injection
        for score, name, info in ranked:
            print(f"\n=== SKILL: {name} (score={score}) ===")
            try:
                content = Path(info["path"]).read_text()
                print(content[:2000])
                if len(content) > 2000:
                    print(f"... [{len(content) - 2000} more chars]")
            except Exception as e:
                print(f"[ERROR reading skill: {e}]")
    else:
        print(f"🎯 Top {len(ranked)} skills for: {args.request[:80]}")
        for score, name, info in ranked:
            print(f"   {score:>4} | {name:<30} | {info['description'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
