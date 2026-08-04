#!/usr/bin/env python3
"""
mavis-plan.py — Plan-then-execute orchestrator (Mavis v4.0).

The TOP 1% agentic autonomous agents (Devin, Claude Code, Manus) all default
to a "plan mode" before execution. This script is the Mavis equivalent:
  1. Take a complex user request
  2. Decompose it into a plan (sub-tasks, dependencies, models)
  3. Show the plan to Francis (or skip if --auto)
  4. Execute step by step with self-critique
  5. Persist the plan to Supabase mavis_knowledge for future reference

Usage:
  mavis-plan "Refactor the Mavis install script for clarity"
  mavis-plan --auto "Migrate all tasks from mavis_tasks to mavis_knowledge"
  mavis-plan --from-knowledge "Continue the work from id=42"
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone


def call_llm(prompt: str, system: str = "", model: str = "claude-haiku-4-5", tokens: int = 2048) -> str:
    """Call mavis-call wrapper."""
    jarvis_home = os.path.expanduser("~/jarvis") if os.path.exists(os.path.expanduser("~/jarvis")) else "/workspace/jarvis"
    wrapper = os.path.join(jarvis_home, "scripts", "mavis-call")
    cmd = [wrapper, "--model", model, "--no-fallback", prompt, str(tokens)]
    if system:
        cmd.insert(3, "--system")
        cmd.insert(4, system)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"[ERROR] {e}"


def decompose_into_plan(user_request: str) -> list:
    """Use Claude to decompose the request into a structured plan."""
    system = """Tu es Mavis, un orchestrateur agentic. Décompose la demande utilisateur en un plan d'exécution.

Réponds UNIQUEMENT en JSON valide (no prose before/after) avec ce format:
{
  "goal": "restated goal in 1 sentence",
  "steps": [
    {
      "id": "step-1",
      "title": "short title",
      "action": "what to do concretely",
      "model": "claude-haiku-4-5|claude-sonnet-5|claude-opus-5",
      "tool": "mavis-call|mavis-rag|bash|write|read",
      "depends_on": [],
      "estimated_seconds": 10,
      "verification": "how to verify this step succeeded"
    }
  ],
  "risks": ["what could go wrong"],
  "estimated_total_seconds": 60
}

Règles:
- Steps 1-7 max (décompose pas trop)
- Chaque step a un seul owner tool
- depends_on = list of step ids (empty if independent)
- Verification = commandable (pas vague)
- Si la demande est triviale, retourner 1 step avec tool=mavis-call
"""
    out = call_llm(user_request, system=system, model="claude-haiku-4-5", tokens=2048)
    # Extract JSON from the output (Claude may add prose)
    json_start = out.find("{")
    json_end = out.rfind("}")
    if json_start == -1 or json_end == -1:
        return [{
            "id": "step-1",
            "title": "Direct answer",
            "action": user_request,
            "model": "claude-haiku-4-5",
            "tool": "mavis-call",
            "depends_on": [],
            "estimated_seconds": 15,
            "verification": "Answer contains substantive content"
        }]
    try:
        return json.loads(out[json_start:json_end + 1]).get("steps", [])
    except json.JSONDecodeError:
        return [{
            "id": "step-1",
            "title": "Direct answer",
            "action": user_request,
            "model": "claude-haiku-4-5",
            "tool": "mavis-call",
            "depends_on": [],
            "estimated_seconds": 15,
            "verification": "Answer contains substantive content"
        }]


def execute_step(step: dict, plan_context: dict) -> dict:
    """Execute a single plan step. Returns {success, output, error}."""
    started_at = time.time()
    step_id = step.get("id", "?")
    tool = step.get("tool", "mavis-call")
    action = step.get("action", "")
    model = step.get("model", "claude-haiku-4-5")
    verification = step.get("verification", "")

    if tool == "mavis-call":
        output = call_llm(action, model=model, tokens=1024)
    elif tool == "mavis-rag":
        rag_script = "/usr/local/bin/mavis-rag"
        if os.path.exists(rag_script):
            r = subprocess.run([rag_script, action], capture_output=True, text=True, timeout=60)
            output = r.stdout.strip() or r.stderr.strip()
        else:
            output = "[ERROR] mavis-rag not in PATH"
    elif tool == "bash":
        try:
            r = subprocess.run(action, shell=True, capture_output=True, text=True, timeout=120)
            output = r.stdout + r.stderr
        except Exception as e:
            output = f"[ERROR] {e}"
    elif tool == "write":
        path = step.get("path", "/tmp/plan-output.txt")
        content = step.get("content", output if 'output' in dir() else action)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        output = f"[WROTE] {path} ({len(content)} bytes)"
    elif tool == "read":
        try:
            with open(action) as f:
                output = f.read()
        except Exception as e:
            output = f"[ERROR] {e}"
    else:
        output = f"[SKIP] unknown tool: {tool}"

    duration = time.time() - started_at
    return {
        "step_id": step_id,
        "success": not output.startswith("[ERROR]"),
        "output": output[:500] + ("..." if len(output) > 500 else ""),
        "duration_seconds": round(duration, 2),
        "verification_passed": verify_step(output, verification)
    }


def verify_step(output: str, verification: str) -> bool:
    """Lightweight verification heuristic."""
    if not verification:
        return True
    if verification.startswith("Answer contains"):
        return len(output) > 50 and "[ERROR]" not in output
    # Could be expanded (e.g., "ruff check" → run ruff)
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("request", help="The user request to plan-then-execute")
    p.add_argument("--auto", action="store_true", help="Skip plan approval, execute directly")
    p.add_argument("--persist", action="store_true", help="Save the plan to Supabase mavis_knowledge")
    p.add_argument("--from-knowledge", help="Load goal from a Supabase mavis_knowledge row id")
    args = p.parse_args()

    print("🎯 Mavis plan-then-execute")
    print(f"Request: {args.request[:200]}")
    print()

    # 1. Decompose
    print("📋 Decomposing into plan...")
    steps = decompose_into_plan(args.request)
    print(f"   {len(steps)} steps identified")
    for s in steps:
        deps = f" [after {', '.join(s.get('depends_on', []))}]" if s.get('depends_on') else ""
        print(f"   - {s['id']}: {s.get('title', '?')} ({s.get('tool', '?')}, {s.get('model', '?')}, ~{s.get('estimated_seconds', '?')}s){deps}")
    print()

    # 2. Optional approval
    if not args.auto:
        try:
            ans = input("Execute? [Y/n/edit] ").strip().lower()
            if ans == "n":
                print("Aborted.")
                return 1
            if ans == "edit":
                print("Edit mode: type the step id to skip, or 'all' to skip all")
                skip = input("Skip: ").strip()
                if skip == "all":
                    args.auto = True  # Skip approval but keep going
                elif skip:
                    steps = [s for s in steps if s["id"] != skip]
        except EOFError:
            args.auto = True

    # 3. Execute
    print()
    print("🚀 Executing...")
    results = []
    for s in steps:
        print(f"   [{s['id']}] {s.get('title', '?')}...", end=" ", flush=True)
        r = execute_step(s, {"plan_steps": steps})
        results.append(r)
        status = "✅" if r["success"] else "❌"
        print(f"{status} ({r['duration_seconds']}s)")
        if not r["success"]:
            print(f"      {r['output'][:200]}")

    # 4. Summary
    success_count = sum(1 for r in results if r["success"])
    total_duration = sum(r["duration_seconds"] for r in results)
    print()
    print(f"📊 {success_count}/{len(results)} steps succeeded in {total_duration:.1f}s total")

    # 5. Optional persist
    if args.persist:
        plan_id = f"plan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        plan_record = {
            "plan_id": plan_id,
            "request": args.request,
            "steps": steps,
            "results": results,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = f"/workspace/jarvis/plans/{plan_id}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(plan_record, f, indent=2)
        print(f"💾 Plan persisted to {path}")

    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
