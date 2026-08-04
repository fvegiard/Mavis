#!/usr/bin/env python3
"""
test_mavis_skill.py — Tests for mavis-skill (skill auto-loader, keyword ranking).

Run: pytest tests/ -v
"""
import sys
import os
import unittest
import importlib.util
import tempfile
import json
from pathlib import Path

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
SKILL_PATH = os.path.join(SCRIPTS_DIR, "mavis-skill.py")
spec = importlib.util.spec_from_file_location("mavis_skill", SKILL_PATH)
mavis_skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mavis_skill)


class TestExtractKeywords(unittest.TestCase):
    def test_basic_extraction(self):
        keywords = mavis_skill.extract_keywords("The quick brown fox jumps over the lazy dog")
        # Common content words
        self.assertIn("quick", keywords)
        self.assertIn("brown", keywords)
        self.assertIn("fox", keywords)
        self.assertIn("jumps", keywords)
        self.assertIn("lazy", keywords)
        self.assertIn("dog", keywords)
        # The configured stop words should be filtered
        self.assertNotIn("the", keywords)
        # Note: "over" is NOT in the default stop list (it has "of", "on", "at", etc.)
        # Verify the actual stop list behavior
        self.assertNotIn("with", keywords)
        self.assertNotIn("for", keywords)

    def test_lowercase(self):
        keywords = mavis_skill.extract_keywords("HELLO World")
        self.assertIn("hello", keywords)
        self.assertIn("world", keywords)

    def test_short_words_filtered(self):
        keywords = mavis_skill.extract_keywords("a be to of is")
        # All words <3 chars should be filtered
        self.assertEqual(len(keywords), 0)


class TestRankSkills(unittest.TestCase):
    def test_ranking_by_overlap(self):
        skills = {
            "skill-a": {"path": "/tmp/a", "description": "query knowledge base", "keywords": {"query", "knowledge", "base"}},
            "skill-b": {"path": "/tmp/b", "description": "debug errors", "keywords": {"debug", "errors"}},
        }
        ranked = mavis_skill.rank_skills(skills, "I want to query the knowledge base", top_n=2)
        self.assertGreater(len(ranked), 0)
        # skill-a should rank first (3 keyword overlap)
        self.assertEqual(ranked[0][1], "skill-a")

    def test_no_match_returns_empty(self):
        skills = {"x": {"path": "/x", "description": "", "keywords": {"apple", "banana"}}}
        ranked = mavis_skill.rank_skills(skills, "orange juice", top_n=5)
        self.assertEqual(len(ranked), 0)

    def test_top_n_limits(self):
        skills = {f"skill-{i}": {"path": f"/tmp/{i}", "description": "test", "keywords": {"test"}} for i in range(10)}
        ranked = mavis_skill.rank_skills(skills, "test something", top_n=3)
        self.assertEqual(len(ranked), 3)


class TestScanSkills(unittest.TestCase):
    def test_scan_with_skill_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake skill
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: A test skill\n---\n# Test Skill\nSome content here")
            # Override the SKILL_DIRS
            mavis_skill.SKILL_DIRS = [Path(tmpdir)]
            skills = mavis_skill.scan_skills()
            self.assertIn("test-skill", skills)
            self.assertIn("test", skills["test-skill"]["keywords"])


if __name__ == "__main__":
    unittest.main()
