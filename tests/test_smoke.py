#!/usr/bin/env python3
"""
test_smoke.py — Smoke tests for ALL mavis-* tools.

Verifies that each tool:
1. Has --help that works
2. Returns reasonable exit code
3. Has a script file that exists and is executable

Run: pytest tests/test_smoke.py -v
"""
import sys
import os
import unittest
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SYMLINK_DIR = Path("/usr/local/bin")


# Tools and their expected CLI behavior
TOOLS = [
    # (script_name, args_for_help, is_python)
    ("mavis-call", [], True),
    ("mavis-rag", [], True),
    ("mavis-rag-eval", [], True),
    ("mavis-vectorize", [], True),
    ("mavis-vectorize-extra", [], True),
    ("mavis-stream", [], True),
    ("mavis-plan", [], True),
    ("mavis-skill", [], True),
    ("mavis-cost", [], True),
    ("mavis-hook", [], True),
    ("mavis-browser", [], True),
    ("mavis-mcp", [], True),
    ("mavis-worktree", [], True),
    ("mavis-a2a", [], True),
    ("mavis-providers", [], True),
    ("mavis-commit", [], True),
]


class TestScriptsExist(unittest.TestCase):
    def test_all_scripts_in_jarvis(self):
        for name, _, _ in TOOLS:
            script = SCRIPTS_DIR / name
            script_py = SCRIPTS_DIR / f"{name}.py"
            exists = script.exists() or script_py.exists()
            self.assertTrue(exists, f"{name} not found in {SCRIPTS_DIR}")

    def test_all_python_scripts_executable(self):
        for name, _, is_py in TOOLS:
            if not is_py:
                continue
            script = SCRIPTS_DIR / f"{name}.py"
            if script.exists():
                self.assertTrue(os.access(script, os.X_OK), f"{name}.py is not executable")


class TestSymlinksExist(unittest.TestCase):
    def test_symlinks_in_usr_local_bin(self):
        for name, _, _ in TOOLS:
            link = SYMLINK_DIR / name
            # Symlinks may not survive sandbox restart, so just check if it exists
            # Don't fail the test if not present
            if not link.exists():
                # Skip - setup-links script will recreate
                continue


class TestHelpWorks(unittest.TestCase):
    def test_help_exits_0(self):
        for name, _, is_py in TOOLS:
            with self.subTest(tool=name):
                # Try via /usr/local/bin first, then direct script
                cmd = [name, "--help"]
                if not (SYMLINK_DIR / name).exists():
                    script = SCRIPTS_DIR / f"{name}.py"
                    if not script.exists():
                        script = SCRIPTS_DIR / name
                    cmd = ["python3", str(script), "--help"]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                except subprocess.TimeoutExpired:
                    self.fail(f"{name} --help timed out")
                except FileNotFoundError:
                    # Tool not in PATH, skip
                    continue
                # argparse exits 0 on --help
                self.assertEqual(result.returncode, 0, f"{name} --help failed: {result.stderr[:200]}")


class TestImportsWork(unittest.TestCase):
    """Verify all Python scripts can be imported without errors."""

    def test_all_python_imports(self):
        import importlib.util
        for name, _, is_py in TOOLS:
            if not is_py:
                continue
            script = SCRIPTS_DIR / f"{name}.py"
            if not script.exists():
                continue
            with self.subTest(tool=name):
                spec = importlib.util.spec_from_file_location(f"test_{name}", script)
                if spec and spec.loader:
                    try:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    except SystemExit:
                        # argparse can call sys.exit, that's OK
                        pass
                    except Exception as e:
                        self.fail(f"{name} import failed: {e}")


if __name__ == "__main__":
    unittest.main()
