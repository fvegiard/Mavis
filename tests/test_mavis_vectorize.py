#!/usr/bin/env python3
"""
test_mavis_vectorize.py — Tests for mavis-vectorize (embeddings + retrieval).

Run: pytest tests/ -v
"""
import sys
import os
import unittest
import importlib.util
import math
import tempfile
import json
from pathlib import Path

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
VEC_PATH = os.path.join(SCRIPTS_DIR, "mavis-vectorize.py")
spec = importlib.util.spec_from_file_location("mavis_vectorize", VEC_PATH)
mv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv)


class TestModuleStructure(unittest.TestCase):
    def test_module_imports(self):
        # Verify the module has the key functions
        self.assertTrue(hasattr(mv, "openai_embed"))
        self.assertTrue(hasattr(mv, "supa_get"))
        self.assertTrue(hasattr(mv, "supa_post"))
        self.assertTrue(hasattr(mv, "main"))
        self.assertTrue(callable(mv.main))


class TestEmbeddingConstants(unittest.TestCase):
    def test_embed_model_is_1536_dim(self):
        # text-embedding-3-small returns 1536 dimensions
        self.assertIn("text-embedding-3-small", mv.EMBED_MODEL)


class TestArgparse(unittest.TestCase):
    def test_help_shows_options(self):
        import subprocess
        result = subprocess.run(["python3", VEC_PATH, "--help"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--text", result.stdout)
        self.assertIn("--row-id", result.stdout)
        self.assertIn("--rebuild", result.stdout)
        self.assertIn("--fetch-cache", result.stdout)


if __name__ == "__main__":
    unittest.main()
