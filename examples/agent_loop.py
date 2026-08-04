#!/usr/bin/env python3
"""
example_agent_loop.py — Example: autonomous agent loop with self-critique.

This shows the pattern for an agent that:
1. Generates an action
2. Executes it
3. Critiques the output
4. Revises if needed (max 3 iterations per Reflexion v2)
5. Returns or escalates

Based on Reflexion (Shinn et al. 2023) and SAGE (2024).
"""
import sys
import subprocess


REFLEXION_SYSTEM = """You are Mavis, a self-improving agent. For each iteration:
1. Generate the next action based on the request + previous attempts
2. After execution, critique the output (what's wrong? what could be better?)
3. If critique says "ship it", output DONE
4. If critique says "fix X", generate the fixed version

After 3 iterations without DONE, output ESCALATE with a brief explanation.
"""


def call_llm(prompt: str, system: str = "") -> str:
    """Call mavis-call directly."""
    cmd = ["mavis-call", "--model", "claude-haiku-4-5", prompt, "1024"]
    if system:
        cmd += ["--system", system]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def execute(action: str) -> str:
    """Execute a shell action. Returns stdout/stderr."""
    try:
        result = subprocess.run(action, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return f"[ERROR] {e}"


def agent_loop(user_request: str, max_iter: int = 3) -> dict:
    """Run the agent loop with self-critique."""
    history = []
    final_output = None

    for i in range(1, max_iter + 1):
        # 1. Generate next action
        history_str = "\n".join([f"[Iter {h['iter']}] Action: {h['action'][:100]}\nOutput: {h['output'][:200]}\nCritique: {h['critique'][:200]}" for h in history])
        gen_prompt = f"""User request: {user_request}

{history_str}

Iteration {i}/{max_iter}. What is the next action? Reply with:
- A shell command to execute (just the command, no prose)
- OR "DONE: <final answer>" if the task is complete
- OR "ESCALATE: <reason>" if stuck
"""
        action = call_llm(gen_prompt, system=REFLEXION_SYSTEM)

        if action.startswith("DONE:"):
            final_output = action[5:].strip()
            break
        if action.startswith("ESCALATE:"):
            final_output = f"[ESCALATED] {action[9:].strip()}"
            break

        # 2. Execute
        output = execute(action)

        # 3. Critique
        crit_prompt = f"""Action: {action}
Output: {output[:500]}

Did this succeed? Reply with:
- "OK" if the action accomplished its goal
- "FAIL: <reason>" if it didn't
- "PARTIAL: <what's still missing>"
"""
        critique = call_llm(crit_prompt)

        history.append({
            "iter": i,
            "action": action,
            "output": output,
            "critique": critique,
        })

        if critique.startswith("OK"):
            # Generate the final answer based on history
            final_prompt = f"""User request: {user_request}

The agent executed this action successfully: {action}
Output: {output[:500]}

Write a concise final answer (1-2 sentences) for the user.
"""
            final_output = call_llm(final_prompt)
            break
    else:
        final_output = f"[MAX ITERATIONS] After {max_iter} iterations, the agent did not converge."

    return {
        "request": user_request,
        "iterations": len(history),
        "final": final_output,
        "history": history,
    }


if __name__ == "__main__":
    request = sys.argv[1] if len(sys.argv) > 1 else "List all Python files in /workspace/jarvis/scripts"
    result = agent_loop(request)
    print(f"Request: {result['request']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Final answer: {result['final']}")
    if result["iterations"] > 1:
        print(f"\nHistory:")
        for h in result["history"]:
            print(f"  [Iter {h['iter']}] {h['action'][:80]}...")
            print(f"           Critique: {h['critique'][:80]}")
