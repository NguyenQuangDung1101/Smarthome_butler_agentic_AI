import json
import random
import re
from pathlib import Path

EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
DETERMINISTIC_REPORT_FILE = "./eval/deterministic_report.json"
LLM_JUDGE_REPORT_FILE = "./eval/llm_judge_report.json"
AGENT_OUTPUT_FILE = "./eval/agent_output.json"

REMOVED_DATASET_FILE = "./eval/removed_eval_dataset_cases.json"

RANDOM_SEED = 42
REMOVE_COUNT = 100


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_id_number(case_id: str) -> int:
    """
    Support ids like:
    tc01, tc1, tc_01, tc_1, tc100
    """
    match = re.search(r"(\d+)$", case_id)
    if not match:
        raise ValueError(f"Invalid id format: {case_id}")
    return int(match.group(1))


def sort_by_id(items):
    return sorted(items, key=lambda x: extract_id_number(x["id"]))


def build_new_id(index: int, use_underscore: bool = False, min_width: int = 2) -> str:
    width = max(min_width, len(str(index)))
    if use_underscore:
        return f"tc_{index:0{width}d}"
    return f"tc{index:0{width}d}"


def detect_id_style(items):
    """
    Detect whether current ids use 'tc_01' or 'tc01'
    """
    if not items:
        return False
    underscore_count = sum(1 for item in items if "_" in item["id"])
    return underscore_count > len(items) / 2


def remap_ids_in_list(items, id_map):
    new_items = []
    for item in items:
        old_id = item["id"]
        if old_id not in id_map:
            continue
        new_item = dict(item)
        new_item["id"] = id_map[old_id]
        new_items.append(new_item)
    return new_items


def rebuild_deterministic_summary(filtered_results, benchmark_ids):
    result_ids = {r["id"] for r in filtered_results}
    benchmark_ids = set(benchmark_ids)

    pass_count = sum(1 for r in filtered_results if r.get("result", "").upper() == "PASS")
    fail_count = sum(1 for r in filtered_results if r.get("result", "").upper() == "FAIL")

    missing_in_benchmark = sorted(result_ids - benchmark_ids, key=extract_id_number)
    missing_in_output = sorted(benchmark_ids - result_ids, key=extract_id_number)

    return {
        "total_cases_in_benchmark": len(benchmark_ids),
        "total_cases_evaluated": len(filtered_results),
        "pass": pass_count,
        "fail": fail_count,
        "missing_in_benchmark": missing_in_benchmark,
        "missing_in_output": missing_in_output
    }


def rebuild_llm_summary(filtered_results, benchmark_ids):
    result_ids = {r["id"] for r in filtered_results}
    benchmark_ids = set(benchmark_ids)

    pass_count = sum(1 for r in filtered_results if r.get("verdict", "").upper() == "PASS")
    fail_count = sum(1 for r in filtered_results if r.get("verdict", "").upper() == "FAIL")

    missing_in_benchmark = sorted(result_ids - benchmark_ids, key=extract_id_number)
    missing_in_output = sorted(benchmark_ids - result_ids, key=extract_id_number)

    return {
        "total_cases_in_benchmark": len(benchmark_ids),
        "total_cases_evaluated": len(filtered_results),
        "pass": pass_count,
        "fail": fail_count,
        "missing_in_benchmark": missing_in_benchmark,
        "missing_in_output": missing_in_output
    }


def main():
    random.seed(RANDOM_SEED)

    eval_data = load_json(EVAL_DATASET_FILE)
    deterministic_report = load_json(DETERMINISTIC_REPORT_FILE)
    llm_judge_report = load_json(LLM_JUDGE_REPORT_FILE)
    agent_output = load_json(AGENT_OUTPUT_FILE)

    # 1) Sort all files by id first
    eval_data = sort_by_id(eval_data)
    deterministic_results = sort_by_id(deterministic_report.get("results", []))
    llm_results = sort_by_id(llm_judge_report.get("results", []))
    agent_output = sort_by_id(agent_output)

    # 2) Find ids that FAIL in both reports
    det_fail_ids = {
        item["id"]
        for item in deterministic_results
        if item.get("result", "").upper() == "FAIL"
    }
    llm_fail_ids = {
        item["id"]
        for item in llm_results
        if item.get("verdict", "").upper() == "FAIL"
    }

    fail_in_both_ids = sorted(det_fail_ids & llm_fail_ids, key=extract_id_number)

    if len(fail_in_both_ids) < REMOVE_COUNT:
        raise ValueError(
            f"Only found {len(fail_in_both_ids)} cases that FAIL in both files, "
            f"but REMOVE_COUNT={REMOVE_COUNT}."
        )

    # 3) Randomly select ids to remove
    ids_to_remove = set(random.sample(fail_in_both_ids, REMOVE_COUNT))

    print(f"Found {len(fail_in_both_ids)} FAIL-in-both cases.")
    print(f"Selected {len(ids_to_remove)} case(s) to remove.\n")

    # 4) Move removed dataset cases to another JSON file (dataset only)
    removed_eval_data = [item for item in eval_data if item["id"] in ids_to_remove]
    removed_eval_data = sort_by_id(removed_eval_data)
    save_json(REMOVED_DATASET_FILE, removed_eval_data)

    print(f"Saved removed dataset cases to: {REMOVED_DATASET_FILE}")

    # 5) Remove selected ids from all 4 files
    filtered_eval_data = [item for item in eval_data if item["id"] not in ids_to_remove]
    filtered_det_results = [item for item in deterministic_results if item["id"] not in ids_to_remove]
    filtered_llm_results = [item for item in llm_results if item["id"] not in ids_to_remove]
    filtered_agent_output = [item for item in agent_output if item["id"] not in ids_to_remove]

    # 6) Sort again after removal
    filtered_eval_data = sort_by_id(filtered_eval_data)
    filtered_det_results = sort_by_id(filtered_det_results)
    filtered_llm_results = sort_by_id(filtered_llm_results)
    filtered_agent_output = sort_by_id(filtered_agent_output)

    # 7) Renumber ids sequentially
    use_underscore = detect_id_style(eval_data)

    old_ids_after_removal = [item["id"] for item in filtered_eval_data]
    id_map = {
        old_id: build_new_id(i + 1, use_underscore=use_underscore, min_width=2)
        for i, old_id in enumerate(old_ids_after_removal)
    }

    filtered_eval_data = remap_ids_in_list(filtered_eval_data, id_map)
    filtered_det_results = remap_ids_in_list(filtered_det_results, id_map)
    filtered_llm_results = remap_ids_in_list(filtered_llm_results, id_map)
    filtered_agent_output = remap_ids_in_list(filtered_agent_output, id_map)

    # 8) Final sort by new id
    filtered_eval_data = sort_by_id(filtered_eval_data)
    filtered_det_results = sort_by_id(filtered_det_results)
    filtered_llm_results = sort_by_id(filtered_llm_results)
    filtered_agent_output = sort_by_id(filtered_agent_output)

    # 9) Rebuild summaries before writing results
    benchmark_ids = [item["id"] for item in filtered_eval_data]

    new_deterministic_report = {
        "summary": rebuild_deterministic_summary(filtered_det_results, benchmark_ids),
        "results": filtered_det_results
    }

    new_llm_judge_report = {
        "summary": rebuild_llm_summary(filtered_llm_results, benchmark_ids),
        "results": filtered_llm_results
    }

    # 10) Save all updated files
    save_json(EVAL_DATASET_FILE, filtered_eval_data)
    save_json(DETERMINISTIC_REPORT_FILE, new_deterministic_report)
    save_json(LLM_JUDGE_REPORT_FILE, new_llm_judge_report)
    save_json(AGENT_OUTPUT_FILE, filtered_agent_output)

    print("\nDone.")
    print(f"Remaining dataset cases       : {len(filtered_eval_data)}")
    print(f"Remaining deterministic cases : {len(filtered_det_results)}")
    print(f"Remaining llm judge cases     : {len(filtered_llm_results)}")
    print(f"Remaining agent output cases  : {len(filtered_agent_output)}")
    print(f"ID style used                 : {'tc_01' if use_underscore else 'tc01'}")

    print("\nRemoved ids:")
    for case_id in sorted(ids_to_remove, key=extract_id_number):
        print(f"  - {case_id}")


if __name__ == "__main__":
    main()