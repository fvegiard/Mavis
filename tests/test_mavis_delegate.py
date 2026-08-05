"""Smoke tests for mavis-delegate."""
import json
import subprocess
import sys
from pathlib import Path

Mavis_DIR = Path(__file__).parent.parent
DELEGATE = Mavis_DIR / "scripts" / "mavis-delegate"


def test_matrix_runs():
    r = subprocess.run([sys.executable, str(DELEGATE), "--matrix"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "openhands" in r.stdout
    assert "hermes" in r.stdout
    assert "maxclaw" in r.stdout
    assert "verifier" in r.stdout


def test_classify_code_task():
    r = subprocess.run([sys.executable, str(DELEGATE), "--dry-run", "fix the failing test"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["agent"] == "openhands"


def test_classify_research_task():
    r = subprocess.run([sys.executable, str(DELEGATE), "--dry-run", "research best 2026 frameworks"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["agent"] == "hermes"


def test_classify_infra_task():
    r = subprocess.run([sys.executable, str(DELEGATE), "--dry-run", "restart nginx on prod"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["agent"] == "maxclaw"


def test_classify_verify_task():
    r = subprocess.run([sys.executable, str(DELEGATE), "--dry-run", "verify this code is correct"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["agent"] == "verifier"


def test_classify_falls_back_to_general():
    r = subprocess.run([sys.executable, str(DELEGATE), "--dry-run", "what's the weather"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["agent"] in ("general", "hermes")  # 'weather' might hit research


if __name__ == "__main__":
    test_matrix_runs()
    test_classify_code_task()
    test_classify_research_task()
    test_classify_infra_task()
    test_classify_verify_task()
    test_classify_falls_back_to_general()
    print("ALL TESTS PASSED")
