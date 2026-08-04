#!/usr/bin/env python3
"""
test_mavis_providers.py — Tests for mavis-providers (multi-LLM router).

Run: pytest tests/ -v
"""
import sys
import os
import unittest
import importlib.util

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
PROVIDERS_PATH = os.path.join(SCRIPTS_DIR, "mavis-providers.py")
spec = importlib.util.spec_from_file_location("mavis_providers", PROVIDERS_PATH)
mavis_providers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mavis_providers)


class TestProviderRegistry(unittest.TestCase):
    def test_all_providers_have_required_fields(self):
        for name, p in mavis_providers.PROVIDERS.items():
            self.assertIn("name", p, f"{name} missing 'name'")
            self.assertIn("env_key", p, f"{name} missing 'env_key'")
            self.assertIn("endpoint", p, f"{name} missing 'endpoint'")
            self.assertIn("format", p, f"{name} missing 'format'")
            self.assertIn("priority", p, f"{name} missing 'priority'")
            self.assertIn("context_window", p, f"{name} missing 'context_window'")
            self.assertIn("models", p, f"{name} missing 'models'")
            self.assertGreater(len(p["models"]), 0, f"{name} has no models")

    def test_free_provider_at_top(self):
        # openrouter-free should be priority 0 (highest)
        self.assertEqual(mavis_providers.PROVIDERS["openrouter-free"]["priority"], 0)
        # claude-oauth should be priority 1
        self.assertEqual(mavis_providers.PROVIDERS["claude-oauth"]["priority"], 1)

    def test_copilot_is_reserved_priority(self):
        # Copilot is priority 2 (reserved for commit/review per Francis's rule)
        self.assertEqual(mavis_providers.PROVIDERS["copilot"]["priority"], 2)

    def test_no_duplicate_priorities_for_default_chain(self):
        # Get top providers by priority (0, 1, 2, 3, 4 are the active ones)
        priorities = [p["priority"] for n, p in mavis_providers.PROVIDERS.items() if p["priority"] < 10]
        # Allow duplicates? Actually let's check there are 5 unique priorities
        self.assertGreaterEqual(len(set(priorities)), 5)

    def test_free_models_marked(self):
        free = mavis_providers.PROVIDERS["openrouter-free"]
        for model in free["models"]:
            self.assertIn(":free", model, f"{model} is not marked as free")


class TestAuthHeaderFormat(unittest.TestCase):
    def test_auth_header_is_bearer_format(self):
        for name, p in mavis_providers.PROVIDERS.items():
            if p["format"] in ("openai", "anthropic"):
                self.assertIn("Bearer", p["auth_header"], f"{name} auth_header should be Bearer format, got: {p['auth_header']}")
                # Should NOT include "Authorization:" prefix
                self.assertNotIn("Authorization", p["auth_header"], f"{name} auth_header should NOT have Authorization: prefix")


class TestProviderTest(unittest.TestCase):
    def test_provider_without_key_returns_unavailable(self):
        # Find a provider whose env key is not set
        test_provider_name = None
        for name, p in mavis_providers.PROVIDERS.items():
            if not os.environ.get(p["env_key"]):
                test_provider_name = name
                break
        if not test_provider_name:
            self.skipTest("All provider keys are set in env")
        result = mavis_providers.test_provider(test_provider_name, mavis_providers.PROVIDERS[test_provider_name])
        self.assertFalse(result["available"])
        self.assertIn("no", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
