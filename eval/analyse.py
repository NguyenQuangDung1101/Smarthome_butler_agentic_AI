import json
from collections import defaultdict

EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
DETERMINISTIC_REPORT_FILE = "./eval/deterministic_report.json"
LLM_JUDGE_REPORT_FILE = "./eval/llm_judge_report.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    eval_data = load_json(EVAL_DATASET_FILE)
    deterministic_report = load_json(DETERMINISTIC_REPORT_FILE)
    llm_judge_report = load_json(LLM_JUDGE_REPORT_FILE)

    # id -> task_type
    id_to_task_type = {item["id"]: item["task_type"] for item in eval_data}

    # id -> result maps
    deterministic_map = {r["id"]: r["result"].upper()
                         for r in deterministic_report["results"]}
    llm_map = {r["id"]: r["verdict"].upper()
               for r in llm_judge_report["results"]}

    # collect fail in both
    fail_both = defaultdict(list)

    for case_id, task_type in id_to_task_type.items():
        if deterministic_map.get(case_id) == "FAIL" and llm_map.get(case_id) == "FAIL":
            fail_both[task_type].append(case_id)

    # ---- TABLE PRINT ----
    max_task_len = max([len(t) for t in fail_both.keys()] + [len("Task Type")])
    col_width = max_task_len + 2

    header = (
        f"{'Task Type'.ljust(col_width)}"
        f"{'FAIL_BOTH':>10}"
        # f"{'CASE_IDS':>50}"
    )

    print("\n=== FAIL in BOTH (Deterministic + LLM Judge) ===\n")
    print(header)
    print("-" * len(header))

    total = 0

    for task_type in sorted(fail_both.keys()):
        case_ids = sorted(fail_both[task_type])
        count = len(case_ids)
        total += count

        case_str = ", ".join(case_ids)

        print(
            f"{task_type.ljust(col_width)}"
            f"{count:>10}"
            # f"{case_str:>50}"
        )

    print("-" * len(header))
    print(
        f"{'TOTAL'.ljust(col_width)}"
        f"{total:>10}"
    )


if __name__ == "__main__":
    main()