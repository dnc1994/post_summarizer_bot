"""
autorater.py — Rate a candidate prompt against eval rubrics.

Given a prompt .txt file (must contain {text} placeholder), generates new summaries
for each example in the dataset, then evaluates all rubrics with an LLM judge.

Usage:
    uv run python eval/autorater.py \\
      --prompt-file eval/prompts/v2.txt \\
      [--dataset eval/data/traces.jsonl] \\
      [--rubrics eval/data/rubrics.json] \\
      [--example-rubrics eval/data/example_rubrics.jsonl] \\
      [--output eval/data/results/v2_<ts>.json] \\
      [--limit 20]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"


def get_gemini_client():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def call_gemini(client, prompt: str, json_output: bool = False) -> str:
    from google.genai import types

    config_kwargs = {"temperature": 0.1}
    if json_output:
        config_kwargs["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text.strip()


def generate_summary(client, prompt_template: str, article_text: str) -> str:
    prompt = prompt_template.replace("{text}", article_text)
    return call_gemini(client, prompt)


def evaluate_rubric(client, statement: str, response: str) -> dict:
    """Evaluate a single rubric statement against a summary. Returns {reasoning, pass}."""
    judge_prompt = f"""You are a strict evaluator of AI-generated article summaries.
Evaluate whether the following statement is TRUE or FALSE for the given summary.

Statement: {statement}

Summary:
---
{response}
---

Think step by step. Output ONLY valid JSON (no markdown fences):
{{"reasoning": "your reasoning here", "pass": true}}"""

    text = call_gemini(client, judge_prompt, json_output=True)
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    result = json.loads(text)
    return {"reasoning": result.get("reasoning", ""), "pass": bool(result.get("pass", False))}


def print_results_table(prompt_file: str, examples: list[dict], principle_rubrics: list[dict]):
    n = len(examples)
    print(f"\nCandidate: {prompt_file}  |  {n} example(s)\n")

    # Principle-based rubrics
    if principle_rubrics:
        print(f"PRINCIPLE-BASED RUBRICS (all {n} examples)")
        col_w = 60
        print(f"{'Rubric':<{col_w}}  {'Pass Rate':>10}")
        print("─" * col_w + "  " + "─" * 10)

        rubric_pass_counts: dict[str, int] = {r["id"]: 0 for r in principle_rubrics}
        rubric_totals: dict[str, int] = {r["id"]: 0 for r in principle_rubrics}

        for ex in examples:
            for res in ex.get("principle_results", []):
                rid = res["id"]
                rubric_totals[rid] = rubric_totals.get(rid, 0) + 1
                if res["pass"]:
                    rubric_pass_counts[rid] = rubric_pass_counts.get(rid, 0) + 1

        total_pass = 0
        total_evals = 0
        per_rubric_stats = []
        for r in principle_rubrics:
            rid = r["id"]
            n_pass = rubric_pass_counts.get(rid, 0)
            n_total = rubric_totals.get(rid, 0)
            rate = n_pass / n_total if n_total else 0
            label = f"{rid}: {r['statement']}"
            if len(label) > col_w:
                label = label[: col_w - 3] + "..."
            print(f"{label:<{col_w}}  {rate * 100:>9.1f}%")
            total_pass += n_pass
            total_evals += n_total
            per_rubric_stats.append({"id": rid, "statement": r["statement"], "pass_rate": rate, "n_pass": n_pass, "n_total": n_total})

        overall = total_pass / total_evals if total_evals else 0
        print(f"{'':>{col_w}}  {'Overall:':>10}")
        print(f"{'':>{col_w}}  {overall * 100:>9.1f}%")
    else:
        print("No principle rubrics loaded.")
        per_rubric_stats = []
        overall = 0.0

    # Example-specific rubrics
    n_with_ex = sum(1 for ex in examples if ex.get("example_results"))
    n_ex_evals = sum(len(ex.get("example_results", [])) for ex in examples)
    n_ex_pass = sum(
        sum(1 for r in ex.get("example_results", []) if r["pass"])
        for ex in examples
    )

    print(f"\nEXAMPLE-SPECIFIC RUBRICS ({n_with_ex} of {n} examples, {n_ex_evals} evaluations)")
    if n_ex_evals:
        ex_overall = n_ex_pass / n_ex_evals
        print(f"{'':>60}  {'Overall:':>10}")
        print(f"{'':>60}  {ex_overall * 100:>9.1f}%")
    else:
        print("  (no example-specific rubrics evaluated)")
        ex_overall = 0.0

    return per_rubric_stats, overall, n_with_ex, n_ex_evals, ex_overall


def main():
    parser = argparse.ArgumentParser(description="Rate a candidate prompt against eval rubrics.")
    parser.add_argument("--prompt-file", required=True, help="Path to prompt .txt file with {text} placeholder")
    parser.add_argument("--dataset", default=str(DATA_DIR / "traces.jsonl"), help="Path to traces.jsonl")
    parser.add_argument("--rubrics", default=str(DATA_DIR / "rubrics.json"), help="Path to rubrics.json")
    parser.add_argument("--example-rubrics", default=str(DATA_DIR / "example_rubrics.jsonl"), help="Path to example_rubrics.jsonl")
    parser.add_argument("--output", default=None, help="Output JSON path (default: auto-named in eval/data/results/)")
    parser.add_argument("--limit", type=int, default=None, help="Max number of examples to evaluate")
    args = parser.parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"Error: prompt file not found: {prompt_path}", file=sys.stderr)
        sys.exit(1)

    prompt_template = prompt_path.read_text()
    if "{text}" not in prompt_template:
        print("Error: prompt file must contain {text} placeholder.", file=sys.stderr)
        sys.exit(1)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset not found: {dataset_path}. Run eval/dump_traces.py first.", file=sys.stderr)
        sys.exit(1)

    rubrics_path = Path(args.rubrics)
    example_rubrics_path = Path(args.example_rubrics)

    # Load data
    traces = load_jsonl(dataset_path)
    traces = [t for t in traces if t.get("article_text")]  # need article text to generate summary
    if args.limit:
        traces = traces[: args.limit]

    principle_rubrics: list[dict] = []
    if rubrics_path.exists():
        with open(rubrics_path) as f:
            principle_rubrics = json.load(f)
        print(f"Loaded {len(principle_rubrics)} principle rubric(s) from {rubrics_path}")
    else:
        print(f"Warning: {rubrics_path} not found. Skipping principle rubrics.")

    example_rubrics_by_trace: dict[str, list[dict]] = {}
    if example_rubrics_path.exists():
        for entry in load_jsonl(example_rubrics_path):
            tid = entry.get("trace_id")
            if tid:
                example_rubrics_by_trace[tid] = entry.get("rubrics", [])
        print(f"Loaded example rubrics for {len(example_rubrics_by_trace)} trace(s)")
    else:
        print(f"Note: {example_rubrics_path} not found. No example-specific rubrics will be evaluated.")

    if not traces:
        print("Error: no usable traces found (need article_text).", file=sys.stderr)
        sys.exit(1)

    print(f"\nEvaluating {len(traces)} example(s) with prompt: {prompt_path}\n")

    client = get_gemini_client()
    evaluated_examples = []

    for i, trace in enumerate(traces, 1):
        trace_id = trace["trace_id"]
        url = trace.get("url", "")
        article_text = trace["article_text"]

        print(f"[{i}/{len(traces)}] trace_id={trace_id}")

        # Generate new summary
        print(f"  Generating summary...")
        try:
            new_response = generate_summary(client, prompt_template, article_text)
        except Exception as e:
            print(f"  Error generating summary: {e}", file=sys.stderr)
            continue

        # Evaluate principle rubrics
        principle_results = []
        for rubric in principle_rubrics:
            print(f"  Evaluating rubric {rubric['id']}...")
            try:
                result = evaluate_rubric(client, rubric["statement"], new_response)
                principle_results.append({"id": rubric["id"], **result})
            except Exception as e:
                print(f"  Warning: rubric {rubric['id']} evaluation failed: {e}", file=sys.stderr)
                principle_results.append({"id": rubric["id"], "reasoning": f"Error: {e}", "pass": False})

        # Evaluate example-specific rubrics
        example_results = []
        ex_rubrics = example_rubrics_by_trace.get(trace_id, [])
        for rubric in ex_rubrics:
            print(f"  Evaluating example rubric {rubric['id']}...")
            try:
                result = evaluate_rubric(client, rubric["statement"], new_response)
                example_results.append({"id": rubric["id"], **result})
            except Exception as e:
                print(f"  Warning: example rubric {rubric['id']} failed: {e}", file=sys.stderr)
                example_results.append({"id": rubric["id"], "reasoning": f"Error: {e}", "pass": False})

        evaluated_examples.append({
            "trace_id": trace_id,
            "url": url,
            "response": new_response,
            "principle_results": principle_results,
            "example_results": example_results,
        })

    # Print results table and collect stats
    per_rubric_stats, principle_overall, n_with_ex, n_ex_evals, ex_overall = print_results_table(
        args.prompt_file, evaluated_examples, principle_rubrics
    )

    # Build output JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output:
        output_path = Path(args.output)
    else:
        results_dir = DATA_DIR / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        stem = prompt_path.stem
        output_path = results_dir / f"{stem}_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "prompt_file": str(prompt_path),
        "timestamp": ts,
        "n_examples": len(evaluated_examples),
        "principle": {
            "overall_pass_rate": principle_overall,
            "per_rubric": per_rubric_stats,
        },
        "example_specific": {
            "n_examples_with_rubrics": n_with_ex,
            "n_total_evaluations": n_ex_evals,
            "overall_pass_rate": ex_overall,
        },
        "examples": evaluated_examples,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
