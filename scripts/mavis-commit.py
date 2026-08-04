#!/usr/bin/env python3
"""
mavis-commit.py — Git commit + AI code review using GitHub Copilot.

Per Francis's rule (2026-08-04): **GitHub Copilot is RESERVED for
commits and code revisions**. This tool enforces that:
  - Reviews staged changes via Copilot (claude-opus-4.7 by default)
  - Suggests improvements
  - Asks for confirmation before committing
  - Uses OAuth-style message generation

Usage:
  mavis-commit                       # stage all + review + commit
  mavis-commit --no-review           # skip review (faster)
  mavis-commit --review-only         # just review, no commit
  mavis-commit -m "fix: login bug"    # commit with custom message
  mavis-commit --model claude-opus-5 # use a different model
"""
import sys
import os
import json
import argparse
import subprocess
from pathlib import Path


COPILOT_DEFAULT_MODEL = "kimi-k2.7-code"  # Cheap, fast, great for code review (Francis 2026-08-04: "Kimi K2.7 très bon")
COPILOT_PREMIUM_MODEL = "claude-opus-4.7"   # Premium for critical reviews


def run(cmd: list, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, cwd="/workspace/jarvis")


def git_status() -> str:
    return run(["git", "status", "--short"]).stdout


def git_diff_staged() -> str:
    return run(["git", "diff", "--staged"]).stdout


def git_diff_unstaged() -> str:
    return run(["git", "diff"]).stdout


def git_log_recent(n: int = 5) -> str:
    return run(["git", "log", f"-{n}", "--oneline"]).stdout


def review_with_copilot(diff: str, model: str) -> str:
    """Send the diff to GitHub Copilot for code review."""
    copilot_token = os.environ.get("GITHUB_COPILOT_OAUTH", "")
    if not copilot_token:
        return "[ERROR] GITHUB_COPILOT_OAUTH not in env. This tool requires Copilot (RESERVED per Francis's rule)."

    # Truncate diff to fit context
    if len(diff) > 50_000:
        diff = diff[:50_000] + "\n\n[... diff truncated to 50KB ...]"

    system_prompt = """You are Mavis, a code review assistant. Review the following git diff and provide:
1. A 1-sentence summary of the change
2. Any issues found (bugs, security risks, performance, style)
3. Suggested improvements (be specific)
4. A suggested commit message in conventional commits format (feat/fix/chore/refactor/etc.)
Keep it under 400 words. Be direct, no fluff."""

    user_prompt = f"```diff\n{diff}\n```\n\nReview this diff."

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1500,
        "temperature": 0.2,
    })

    import urllib.request
    req = urllib.request.Request(
        "https://api.githubcopilot.com/chat/completions",
        data=payload.encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {copilot_token}",
            "User-Agent": "Mavis/5.0 (compatible; +https://MiniMax.local/mavis)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "[no content]")
    except Exception as e:
        return f"[ERROR] Copilot review failed: {e}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-m", "--message", help="Custom commit message")
    p.add_argument("--no-review", action="store_true", help="Skip AI review")
    p.add_argument("--review-only", action="store_true", help="Just review, no commit")
    p.add_argument("--model", default=COPILOT_DEFAULT_MODEL, help=f"Copilot model for review (default: {COPILOT_DEFAULT_MODEL})")
    p.add_argument("--premium", action="store_true", help=f"Use premium model ({COPILOT_PREMIUM_MODEL}) for critical reviews")
    p.add_argument("--stage-all", action="store_true", help="git add -A first")
    p.add_argument("--push", action="store_true", help="git push to origin/main after commit")
    args = p.parse_args()

    # Check we're in a git repo
    if run(["git", "rev-parse", "--git-dir"]).returncode != 0:
        print("[ERROR] Not in a git repo", file=sys.stderr)
        return 1

    print("🔍 Git status:")
    status = git_status()
    if not status:
        print("   (no changes)")
        if args.review_only:
            return 0
        # Nothing to commit
        return 0
    print(status)
    print()

    # Optionally stage all
    if args.stage_all:
        print("📦 git add -A...")
        run(["git", "add", "-A"])
        print()

    # Get diff (staged or unstaged)
    diff = git_diff_staged() or git_diff_unstaged()
    if not diff.strip():
        print("[ERROR] No diff to review. Stage some changes first.", file=sys.stderr)
        return 1

    print(f"📊 Diff size: {len(diff):,} bytes, {len(diff.splitlines())} lines")
    print()

    # Review
    if not args.no_review:
        model_to_use = COPILOT_PREMIUM_MODEL if args.premium else args.model
        print(f"🤖 Reviewing via Copilot ({model_to_use})...")
        if args.premium:
            print(f"   (premium mode)")
        print("   (Copilot is RESERVED for commits/reviews per Francis 2026-08-04)")
        print()
        review = review_with_copilot(diff, model_to_use)
        print("=" * 60)
        print("📋 CODE REVIEW")
        print("=" * 60)
        print(review)
        print("=" * 60)
        print()

    if args.review_only:
        return 0

    # Build commit message
    if args.message:
        msg = args.message
    else:
        # Try to extract a suggested message from the review
        if "Suggested commit message" in (review if not args.no_review else ""):
            for line in (review if not args.no_review else "").split("\n"):
                if "Suggested commit message" in line or line.strip().startswith(("feat:", "fix:", "chore:", "refactor:", "docs:", "test:", "perf:")):
                    msg = line.strip().lstrip("*- ").lstrip("`").rstrip("`")
                    if len(msg) > 10:
                        break
            else:
                msg = "chore: update files"
        else:
            msg = "chore: update files"

    # Confirm
    try:
        ans = input(f"💬 Commit message: '{msg}'\n   Proceed? [Y/n/e(dit)] ").strip().lower()
        if ans == "n":
            print("Aborted.")
            return 1
        if ans in ("e", "edit"):
            msg = input("   New message: ").strip()
    except EOFError:
        # No TTY, proceed with default
        pass

    # Commit
    print(f"✅ Committing with: {msg}")
    r = run(["git", "commit", "-m", msg])
    print(r.stdout)
    if r.returncode != 0:
        print(f"[ERROR] {r.stderr}", file=sys.stderr)
        return 1

    # Show last commit
    print("📜 Last commit:")
    print(git_log_recent(1))

    # Optional push
    if args.push:
        remote_check = run(["git", "remote", "get-url", "origin"])
        if remote_check.returncode != 0:
            print("[WARN] No 'origin' remote. Skipping push.", file=sys.stderr)
            return 0
        print()
        print("🚀 Pushing to origin/main...")
        push_result = run(["git", "push", "origin", "main"], capture=False)
        if push_result.returncode != 0:
            print(f"[ERROR] Push failed", file=sys.stderr)
            return 1
        print("✅ Pushed to GitHub")
    return 0


if __name__ == "__main__":
    sys.exit(main())
