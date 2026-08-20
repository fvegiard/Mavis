#!/usr/bin/env python3
"""
skill_matcher.py — Pick the right skill(s) for a task.

Pulls all skills (with enriched metadata) from mavis.items,
scores each by keyword overlap with the task description,
returns top-N with rationale.

Usage:
  python3 skill_matcher.py "Refactor the user auth module with test coverage"
  python3 skill_matcher.py "Research 5 competitors in the RAG space" --top 3
  python3 skill_matcher.py "Audit my Supabase project for RLS issues" --json
"""
import argparse, json, os, re, subprocess, sys
from collections import Counter

SUPABASE_KEY = os.environ.get('SUPABASEMGMT_API_KEY') or os.environ.get('MAVIS_TOKEN')
REF = 'tuwshovazpqzsvwnicgj'

# Stopwords (FR + EN) — we don't want to score on these
STOP = set("""
a an the of and or but if then else for with on at to from in into onto
is are was were be been being have has had do does did will would should could may might
le la les un une des du de et ou mais si pour avec sur dans par vers
ce cette ces ça cela
""".split())

def tokenize(text):
    """Lowercase, split on non-alphanum, drop stopwords and short tokens."""
    if not text: return []
    toks = re.findall(r"[a-zA-ZÀ-ÿ0-9_]+", text.lower())
    return [t for t in toks if t not in STOP and len(t) > 2]

def fetch_skills():
    """Pull all enriched skills from mavis.items via Supabase mgmt API."""
    r = subprocess.run([
      "curl", "-fsS", "--max-time", "30",
      "-X", "POST",
      f"https://api.supabase.com/v1/projects/{REF}/database/query",
      "-H", "Authorization: Bearer " + SUPABASE_KEY,
      "-H", "Content-Type: application/json",
      "-d", json.dumps({"query": "SELECT name, description, payload, triggers FROM mavis.items WHERE category='skill'"}),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: {r.stderr[:200]}", file=sys.stderr); sys.exit(1)
    rows = json.loads(r.stdout)
    skills = []
    for row in rows:
        payload = row.get("payload") or {}
        # If the row is a stringified JSON, parse it
        if isinstance(payload, str):
            try: payload = json.loads(payload)
            except: payload = {}
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        if not summary:
            # Unenriched skill — fallback to triggers + description
            summary = {"when_to_use": [], "phases": [], "related": [], "use_cases": []}
        skills.append({
            "name": row["name"],
            "description": row.get("description", ""),
            "triggers": row.get("triggers", []),
            "summary": summary,
        })
    return skills

def score_skill(skill, task_tokens):
    """Score a skill against task tokens. Higher = better match."""
    # Build a corpus from the skill's matchable text
    corpus_parts = [
        skill["description"] or "",
        " ".join(skill["triggers"] or []),
        " ".join(skill["summary"].get("when_to_use", [])),
        " ".join(skill["summary"].get("use_cases", [])),
        " ".join(skill["summary"].get("phases", [])),
        " ".join(skill["summary"].get("related", [])),
        " ".join(skill["summary"].get("deliverable", []) if isinstance(skill["summary"].get("deliverable"), list) else [skill["summary"].get("deliverable", "")]),
    ]
    corpus = " ".join(corpus_parts).lower()
    corpus_tokens = tokenize(corpus)
    corpus_freq = Counter(corpus_tokens)
    task_freq = Counter(task_tokens)

    # TF-IDF-ish score: sum of (task_freq * corpus_freq) for matching tokens
    # normalized by total tokens to avoid long-corpus bias
    score = 0
    for tok, tf in task_freq.items():
        if tok in corpus_freq:
            score += tf * corpus_freq[tok]
    # Length penalty: longer corpus is harder to match perfectly
    if corpus_tokens:
        score = score / (1 + 0.01 * len(corpus_tokens))
    # Bonus: exact trigger matches
    triggers_lower = set((skill.get("triggers") or []))
    for trig in triggers_lower:
        for tt in task_tokens:
            if tt in trig.lower():
                score += 5
    # Bonus: when_to_use phrases contain multi-word matches
    for wtu in skill["summary"].get("when_to_use", []):
        wtu_tokens = set(tokenize(wtu))
        overlap = wtu_tokens & set(task_tokens)
        if len(overlap) >= 2:
            score += 3 * len(overlap)
    return score

def match(task: str, skills: list, top: int = 5):
    """Return top-N skills for a task, sorted by score."""
    task_tokens = tokenize(task)
    if not task_tokens:
        return []
    scored = []
    for s in skills:
        sc = score_skill(s, task_tokens)
        if sc > 0:
            # Pick the best when_to_use as rationale
            best_rationale = ""
            best_overlap = 0
            for wtu in s["summary"].get("when_to_use", []):
                ov = len(set(tokenize(wtu)) & set(task_tokens))
                if ov > best_overlap:
                    best_overlap = ov
                    best_rationale = wtu
            scored.append({
                "name": s["name"],
                "score": round(sc, 2),
                "rationale": best_rationale or "keyword match in description/triggers",
                "deliverable": s["summary"].get("deliverable", ""),
            })
    scored.sort(key=lambda x: -x["score"])
    return scored[:top]

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Pick the right skill(s) for a task")
    p.add_argument("task", help="Task description")
    p.add_argument("--top", "-n", type=int, default=5, help="Number of skills to return")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args()

    skills = fetch_skills()
    print(f"Loaded {len(skills)} skills from mavis.items (enriched: {sum(1 for s in skills if s['summary'])})", file=sys.stderr)
    results = match(args.task, skills, args.top)
    if args.json:
        print(json.dumps({"task": args.task, "matched": results}, indent=2, ensure_ascii=False))
    else:
        print(f"\nTop {len(results)} skills for: \"{args.task}\"\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']}  (score={r['score']})")
            print(f"   WHY: {r['rationale']}")
            if r.get('deliverable'):
                print(f"   DELIVERS: {r['deliverable'][:120]}")
            print()
