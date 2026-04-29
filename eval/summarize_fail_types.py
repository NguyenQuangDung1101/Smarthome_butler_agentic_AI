"""
Summarize fail types across all deterministic_report_*.json files in the eval directory.
"""

import json
import glob
import os
from collections import Counter, defaultdict

# ── Input paths ──────────────────────────────────────────────────────────────
EVAL_DIR = os.path.join(os.path.dirname(__file__))
REPORT_PATTERN = os.path.join(EVAL_DIR, "**", "deterministic_report_gemini_4fewshot.json")
# ─────────────────────────────────────────────────────────────────────────────


def load_report(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def summarize_file(path: str) -> dict:
    """Return per-file stats: total, pass, fail, and fail_type counts."""
    data = load_report(path)
    summary = data.get("summary", {})
    results = data.get("results", [])

    fail_type_counter: Counter = Counter()
    for case in results:
        for ft in case.get("fail_types", []):
            fail_type_counter[ft] += 1

    return {
        "path": path,
        "total": summary.get("total_cases_evaluated", len(results)),
        "pass": summary.get("pass", 0),
        "fail": summary.get("fail", 0),
        "fail_types": dict(fail_type_counter),
    }


def main():
    report_paths = sorted(glob.glob(REPORT_PATTERN, recursive=True))

    if not report_paths:
        print(f"No deterministic_report_*.json files found under: {EVAL_DIR}")
        return

    all_stats = [summarize_file(p) for p in report_paths]

    # ── Per-file table ────────────────────────────────────────────────────────
    print("=" * 80)
    print(f"{'FILE':<55} {'TOTAL':>6} {'PASS':>6} {'FAIL':>6}")
    print("=" * 80)
    for s in all_stats:
        label = os.path.relpath(s["path"], EVAL_DIR)
        print(f"{label:<55} {s['total']:>6} {s['pass']:>6} {s['fail']:>6}")
        for ft, count in sorted(s["fail_types"].items(), key=lambda x: -x[1]):
            print(f"    {ft:<51} {count:>6}")
    print("=" * 80)

    # ── Aggregate across all files ────────────────────────────────────────────
    aggregate: Counter = Counter()
    for s in all_stats:
        aggregate.update(s["fail_types"])

    total_cases = sum(s["total"] for s in all_stats)
    total_pass  = sum(s["pass"]  for s in all_stats)
    total_fail  = sum(s["fail"]  for s in all_stats)

    print(f"\nAGGREGATE  ({len(all_stats)} report files)")
    print(f"  Total cases : {total_cases}")
    print(f"  Pass        : {total_pass}")
    print(f"  Fail        : {total_fail}")
    print()
    print(f"  {'FAIL TYPE':<45} {'COUNT':>6}  {'% of FAIL':>9}")
    print(f"  {'-'*45}  {'-'*6}  {'-'*9}")
    for ft, count in sorted(aggregate.items(), key=lambda x: -x[1]):
        pct = (count / total_fail * 100) if total_fail else 0
        print(f"  {ft:<45} {count:>6}  {pct:>8.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
