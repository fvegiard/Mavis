#!/usr/bin/env python3
"""
test_mavis_cost.py — Tests for mavis-cost (cost analytics, pricing).

Run: pytest tests/ -v
"""
import sys
import os
import unittest
import importlib.util
import tempfile

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
COST_PATH = os.path.join(SCRIPTS_DIR, "mavis-cost.py")
spec = importlib.util.spec_from_file_location("mavis_cost", COST_PATH)
mavis_cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mavis_cost)


class TestCostFor(unittest.TestCase):
    def test_haiku_4_5_pricing(self):
        # 1M input tokens, 1M output tokens
        cost = mavis_cost.cost_for("claude-haiku-4-5", 1_000_000, 1_000_000)
        # $0.80 + $4.00 = $4.80
        self.assertAlmostEqual(cost, 4.80, places=2)

    def test_sonnet_5_pricing(self):
        cost = mavis_cost.cost_for("claude-sonnet-5", 1_000_000, 1_000_000)
        # $5.00 + $25.00 = $30.00
        self.assertAlmostEqual(cost, 30.00, places=2)

    def test_opus_5_pricing(self):
        cost = mavis_cost.cost_for("claude-opus-5", 1_000_000, 1_000_000)
        # $25.00 + $125.00 = $150.00
        self.assertAlmostEqual(cost, 150.00, places=2)

    def test_cache_read_savings(self):
        # 1M input tokens with cache hit
        cost = mavis_cost.cost_for("claude-haiku-4-5", 1_000_000, 0, cache_read=1_000_000)
        # $0.80 + $0.08 = $0.88 (10x cheaper than full input)
        self.assertAlmostEqual(cost, 0.88, places=2)

    def test_unknown_model_falls_back(self):
        # Should not crash, returns a cost (using haiku pricing as fallback)
        cost = mavis_cost.cost_for("claude-unknown-model", 1000, 500)
        self.assertGreater(cost, 0)


class TestRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.write("[]")
        self.tmp.close()
        # Override the default path
        from pathlib import Path
        mavis_cost.COST_LOG = Path(self.tmp.name)
        mavis_cost.PRICING["claude-test-model"] = {"input": 1.0, "output": 2.0, "cache_read": 0.1, "cache_write": 1.0}

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_record_appends_to_log(self):
        mavis_cost.record("claude-haiku-4-5", 1000, 500, label="test")
        entries = mavis_cost.load_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["model"], "claude-haiku-4-5")
        self.assertEqual(entries[0]["input"], 1000)
        self.assertEqual(entries[0]["output"], 500)

    def test_cost_calculated_correctly(self):
        mavis_cost.record("claude-haiku-4-5", 1_000_000, 0)
        entries = mavis_cost.load_log()
        # $0.80 per 1M input
        self.assertAlmostEqual(entries[0]["cost_usd"], 0.80, places=2)


class TestSummarize(unittest.TestCase):
    def test_summarize_empty(self):
        # Just check it doesn't crash on empty input
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            mavis_cost.summarize([], "all")
        output = f.getvalue()
        self.assertIn("Total cost: $0.0000", output)

    def test_summarize_with_entries(self):
        entries = [
            {"model": "claude-haiku-4-5", "input": 1000, "output": 500, "cost_usd": 0.0028, "timestamp": "2026-08-04T10:00:00"},
            {"model": "claude-sonnet-5", "input": 5000, "output": 2000, "cost_usd": 0.075, "timestamp": "2026-08-04T10:01:00"},
        ]
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            mavis_cost.summarize(entries, "all")
        output = f.getvalue()
        self.assertIn("claude-haiku-4-5", output)
        self.assertIn("claude-sonnet-5", output)
        self.assertIn("0.0778", output)  # Total


if __name__ == "__main__":
    unittest.main()
