"""
autorater.py — Rate a candidate prompt against eval rubrics.

Given a prompt .txt file (must contain {text} placeholder), generates new summaries
for each example in the dataset, then evaluates all rubrics with an LLM judge.

Usage:
    uv run python eval/autorater.py --version v1 --prompt-file eval/prompts/v2.txt [--limit 20]

File paths default to eval/data/<version>/ and can be overridden individually.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    result = json.loads(text)
    return {"reasoning": result.get("reasoning", ""), "pass": bool(result.get("pass", False))}


def print_results_table(prompt_file: str, examples: list[dict], principle_rubrics: list[dict]):
    n = len(examples)
    print(f"\nCandidate: {prompt_file}  |  {n} example(s)\n")

    if principle_rubrics:
        print(f"PRINCIPLE-BASED RUBRICS (all {n} examples)")
        col_w = 60
        print(f"{'Rubric':<{col_w}}  {'Pass Rate':>10}")
        print("─" * col_w + "  " + "─" * 10)

        rubric_pass: dict[str, int] = {r["id"]: 0 for r in principle_rubrics}
        rubric_total: dict[str, int] = {r["id"]: 0 for r in principle_rubrics}

        for ex in examples:
            for res in ex.get("principle_results", []):
                rid = res["id"]
                rubric_total[rid] = rubric_total.get(rid, 0) + 1
                if res["pass"]:
                    rubric_pass[rid] = rubric_pass.get(rid, 0) + 1

        total_pass = 0
        total_evals = 0
        per_rubric_stats = []
        for r in principle_rubrics:
            rid = r["id"]
            n_pass = rubric_pass.get(rid, 0)
            n_total = rubric_total.get(rid, 0)
            rate = n_pass / n_total if n_total else 0
            label = f"{rid}: {r['statement']}"
            if len(label) > col_w:
                label = label[:col_w - 3] + "..."
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
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    parser.add_argument("--prompt-file", required=True, help="Prompt .txt file with {text} placeholder")
    parser.add_argument("--dataset", default=None, help="Override examples.jsonl path")
    parser.add_argument("--rubrics", default=None, help="Override rubrics.json path")
    parser.add_argument("--example-rubrics", default=None, help="Override example_rubrics.jsonl path")
    parser.add_argument("--output", default=None, help="Override output JSON path")
    parser.add_argument("--limit", type=int, default=None, help="Max number of examples to evaluate")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / args.version
    dataset_path = Path(args.dataset) if args.dataset else data_dir / "examples.jsonl"
    rubrics_path = Path(args.rubrics) if args.rubrics else data_dir / "global_rubrics.jsonl"
    example_rubrics_path = Path(args.example_rubrics) if args.example_rubrics else data_dir / "example_rubrics.jsonl"

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        print(f"Error: prompt file not found: {prompt_path}", file=sys.stderr)
        sys.exit(1)

    prompt_template = prompt_path.read_text()
    if "{text}" not in prompt_template:
        print("Error: prompt file must contain {text} placeholder.", file=sys.stderr)
        sys.exit(1)

    if not dataset_path.exists():
        print(f"Error: dataset not found: {dataset_path}. Run dump_traces.py --version {args.version} first.", file=sys.stderr)
        sys.exit(1)

    traces = load_jsonl(dataset_path)
    traces = [t for t in traces if t.get("article_text")]

    # Filter by eval_ready field embedded in each trace record
    eval_ready_ids = {t["trace_id"] for t in traces if t.get("eval_ready")}
    if eval_ready_ids:
        original_count = len(traces)
        traces = [t for t in traces if t["trace_id"] in eval_ready_ids]
        print(f"Filtered to {len(traces)} eval-ready trace(s) (of {original_count} total)")
    else:
        print("Note: no eval_ready traces found — evaluating all traces")

    if args.limit:
        traces = traces[:args.limit]

    principle_rubrics: list[dict] = []
    if rubrics_path.exists():
        # global_rubrics.jsonl uses JSONL format (one rubric per line)
        principle_rubrics = load_jsonl(rubrics_path)
        print(f"Loaded {len(principle_rubrics)} principle rubric(s) from {rubrics_path}")
    else:
        print(f"Warning: {rubrics_path} not found. Skipping principle rubrics.")

    example_rubrics_by_trace: dict[str, list[dict]] = {}
    if example_rubrics_path.exists():
        # Handle duplicate trace_ids: use latest entry per trace
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

    print(f"\nVersion: {args.version} | Evaluating {len(traces)} example(s) with: {prompt_path}\n")

    client = get_gemini_client()
    evaluated_examples = []

    for i, trace in enumerate(traces, 1):
        trace_id = trace["trace_id"]
        print(f"[{i}/{len(traces)}] trace_id={trace_id}")

        print(f"  Generating summary...")
        try:
            new_response = generate_summary(client, prompt_template, trace["article_text"])
        except Exception as e:
            print(f"  Error generating summary: {e}", file=sys.stderr)
            continue

        principle_results = []
        for rubric in principle_rubrics:
            print(f"  Evaluating rubric {rubric['id']}...")
            try:
                result = evaluate_rubric(client, rubric["statement"], new_response)
                principle_results.append({"id": rubric["id"], **result})
            except Exception as e:
                print(f"  Warning: rubric {rubric['id']} failed: {e}", file=sys.stderr)
                principle_results.append({"id": rubric["id"], "reasoning": f"Error: {e}", "pass": False})

        example_results = []
        for rubric in example_rubrics_by_trace.get(trace_id, []):
            print(f"  Evaluating example rubric {rubric['id']}...")
            try:
                result = evaluate_rubric(client, rubric["statement"], new_response)
                example_results.append({"id": rubric["id"], **result})
            except Exception as e:
                print(f"  Warning: example rubric {rubric['id']} failed: {e}", file=sys.stderr)
                example_results.append({"id": rubric["id"], "reasoning": f"Error: {e}", "pass": False})

        evaluated_examples.append({
            "trace_id": trace_id,
            "url": trace.get("url", ""),
            "response": new_response,
            "principle_results": principle_results,
            "example_results": example_results,
        })

    per_rubric_stats, principle_overall, n_with_ex, n_ex_evals, ex_overall = print_results_table(
        args.prompt_file, evaluated_examples, principle_rubrics
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output:
        output_path = Path(args.output)
    else:
        results_dir = data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        output_path = results_dir / f"{prompt_path.stem}_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "version": args.version,
        "prompt_file": str(prompt_path),
        "timestamp": ts,
        "n_examples": len(evaluated_examples),
        "principle": {"overall_pass_rate": principle_overall, "per_rubric": per_rubric_stats},
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
