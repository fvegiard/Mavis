#!/usr/bin/env python3
"""
mavis-worktree.py — Git worktree workflow for Mavis.

The top 1% agents (Claude Code, Cursor) use git worktrees for isolated
development. This script is Mavis's:

Usage:
  mavis-worktree create <branch>          # create new worktree for branch
  mavis-worktree list                      # list active worktrees
  mavis-worktree switch <branch>          # switch context to a worktree
  mavis-worktree merge <branch>           # merge worktree branch back
  mavis-worktree clean                    # remove merged worktrees
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

WORKTREE_BASE = Path(os.environ.get("MAVIS_WORKTREE_BASE", "/workspace/worktrees"))


def run(cmd: list, cwd: str | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)


def in_git_repo() -> bool:
    return run(["git", "rev-parse", "--git-dir"]).returncode == 0


def repo_root() -> str:
    return run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()


def main_branch() -> str:
    out = run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"]).stdout.strip()
    if out:
        return out.split("/")[-1]
    # Fallback: try main, then master
    for branch in ("main", "master", "develop"):
        if run(["git", "show-ref", "--verify", f"refs/heads/{branch}"]).returncode == 0:
            return branch
    return "main"


def list_worktrees() -> list:
    out = run(["git", "worktree", "list", "--porcelain"]).stdout
    worktrees = []
    current = {}
    for line in out.split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current["head"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
    if current:
        worktrees.append(current)
    return worktrees


def cmd_create(args):
    if not in_git_repo():
        print("[ERROR] Not in a git repo. Run 'git init' first.", file=sys.stderr)
        return 1
    repo_root()
    branch = args.branch
    wt_path = WORKTREE_BASE / branch
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    # Create branch if not exists
    existing = run(["git", "show-ref", "--verify", f"refs/heads/{branch}"]).returncode == 0
    if not existing:
        base = args.base or main_branch()
        r = run(["git", "branch", branch, base])
        if r.returncode != 0:
            print(f"[ERROR] git branch: {r.stderr}", file=sys.stderr)
            return 1
    # Add worktree
    r = run(["git", "worktree", "add", str(wt_path), branch])
    if r.returncode != 0:
        print(f"[ERROR] git worktree add: {r.stderr}", file=sys.stderr)
        return 1
    print(f"✅ Created worktree at {wt_path} on branch '{branch}'")
    print(f"   cd {wt_path}")
    return 0


def cmd_list(args):
    if not in_git_repo():
        print("[ERROR] Not in a git repo", file=sys.stderr)
        return 1
    wts = list_worktrees()
    print(f"🌳 {len(wts)} worktree(s):")
    for wt in wts:
        marker = "→" if wt["path"] == os.getcwd() else " "
        print(f"   {marker} {wt['branch']:<30} {wt['path']}")
    return 0


def cmd_switch(args):
    wt_path = WORKTREE_BASE / args.branch
    if not wt_path.exists():
        print(f"[ERROR] Worktree does not exist: {wt_path}", file=sys.stderr)
        print(f"   Create it: mavis-worktree create {args.branch}", file=sys.stderr)
        return 1
    # We can't actually chdir the parent process, but we can output the path
    print(str(wt_path))
    return 0


def cmd_merge(args):
    if not in_git_repo():
        print("[ERROR] Not in a git repo", file=sys.stderr)
        return 1
    branch = args.branch
    main = main_branch()
    if branch == main:
        print("[ERROR] Cannot merge main into itself", file=sys.stderr)
        return 1
    # Switch to main, merge
    r = run(["git", "checkout", main])
    if r.returncode != 0:
        print(f"[ERROR] checkout {main}: {r.stderr}", file=sys.stderr)
        return 1
    r = run(["git", "merge", "--no-ff", branch, "-m", f"merge {branch}"])
    if r.returncode != 0:
        print(f"[ERROR] merge: {r.stderr}", file=sys.stderr)
        return 1
    print(f"✅ Merged '{branch}' into '{main}'")
    return 0


def cmd_clean(args):
    wts = list_worktrees()
    current = os.getcwd()
    cleaned = 0
    for wt in wts:
        if wt["path"] == current:
            continue
        # Remove worktree
        r = run(["git", "worktree", "remove", wt["path"], "--force"])
        if r.returncode == 0:
            cleaned += 1
            print(f"   removed: {wt['path']}")
    print(f"🧹 Cleaned {cleaned} worktree(s)")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("create", help="Create a worktree for a branch")
    p_c.add_argument("branch")
    p_c.add_argument("--base", help="Base branch (default: main)")

    sub.add_parser("list", help="List worktrees")

    p_s = sub.add_parser("switch", help="Get worktree path for a branch")
    p_s.add_argument("branch")

    p_m = sub.add_parser("merge", help="Merge a worktree branch back to main")
    p_m.add_argument("branch")

    sub.add_parser("clean", help="Remove inactive worktrees")

    args = p.parse_args()

    cmds = {
        "create": cmd_create,
        "list": cmd_list,
        "switch": cmd_switch,
        "merge": cmd_merge,
        "clean": cmd_clean,
    }
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
