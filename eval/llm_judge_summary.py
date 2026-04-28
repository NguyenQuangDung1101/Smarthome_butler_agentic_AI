"""
LLM Judge Summary Script
Aggregates 3 LLM judge report files. For each test case, PASS if >= 2 out of 3 runs are PASS.
Configure INPUT_FILES below to point to the 3 report files.
"""

import json
import sys
from pathlib import Path

# ── Configure input files here ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

INPUT_FILES = [
    BASE_DIR / "gemini-3-flash-preview-cloud-4fewshot" / "llm_judge_report_gemini_4fewshot_1.json",
    BASE_DIR / "gemini-3-flash-preview-cloud-4fewshot" / "llm_judge_report_gemini_4fewshot_2.json",
    BASE_DIR / "gemini-3-flash-preview-cloud-4fewshot" / "llm_judge_report_gemini_4fewshot_3.json",
]

OUTPUT_FILE = INPUT_FILES[0].parent / "llm_judge_summary.json"
# ─────────────────────────────────────────────────────────────────────────────


def load_report(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def aggregate_verdicts(report_files: list) -> dict:
    reports = [load_report(f) for f in report_files]

    # Collect all TC ids across all reports
    all_ids = set()
    for report in reports:
        for result in report.get("results", []):
            all_ids.add(result["id"])

    # Build a dict: tc_id -> list of verdicts (one per report)
    tc_verdicts: dict[str, list[str]] = {tc_id: [] for tc_id in all_ids}
    for report in reports:
        result_map = {r["id"]: r for r in report.get("results", [])}
        for tc_id in all_ids:
            if tc_id in result_map:
                tc_verdicts[tc_id].append(result_map[tc_id]["verdict"])
            else:
                tc_verdicts[tc_id].append("MISSING")

    aggregated_results = []
    pass_count = 0
    fail_count = 0

    for tc_id in sorted(all_ids, key=lambda x: (len(x), x)):
        verdicts = tc_verdicts[tc_id]
        num_pass = sum(1 for v in verdicts if v == "PASS")
        final_verdict = "PASS" if num_pass >= 2 else "FAIL"

        if final_verdict == "PASS":
            pass_count += 1
        else:
            fail_count += 1

        aggregated_results.append({
            "id": tc_id,
            "final_verdict": final_verdict,
            "verdicts_per_run": verdicts,
            "pass_count": num_pass,
        })

    total = pass_count + fail_count
    summary = {
        "total_cases": total,
        "pass": pass_count,
        "fail": fail_count,
        "pass_rate": round(pass_count / total * 100, 2) if total > 0 else 0.0,
    }

    return {"summary": summary, "results": aggregated_results}


def main():
    for f in INPUT_FILES:
        if not Path(f).exists():
            print(f"Error: file not found: {f}")
            sys.exit(1)

    output = aggregate_verdicts(INPUT_FILES)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    s = output["summary"]
    print(f"Summary saved to: {OUTPUT_FILE}")
    print(f"Total TCs : {s['total_cases']}")
    print(f"PASS      : {s['pass']} ({s['pass_rate']}%)")
    print(f"FAIL      : {s['fail']}")


if __name__ == "__main__":
    main()
