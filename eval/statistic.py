import json
from collections import defaultdict

EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
REPORT_FILE = "./eval/temp.json"


def main():
    with open(EVAL_DATASET_FILE, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    id_to_task_type = {item["id"]: item["task_type"] for item in eval_data}

    stats = defaultdict(lambda: {"PASS": 0, "FAIL": 0})

    for result in report_data["results"]:
        case_id = result["id"]
        outcome = result["result"]

        if case_id not in id_to_task_type:
            continue

        stats[id_to_task_type[case_id]][outcome] += 1

    # ---- Dynamic column width ----
    max_task_len = max(len(t) for t in stats.keys())
    col_width = max(max_task_len, len("Task Type")) + 2

    header = (
        f"{'Task Type'.ljust(col_width)}"
        f"{'PASS':>8}"
        f"{'FAIL':>8}"
        f"{'TOTAL':>8}"
        f"{'ACC (%)':>10}"
    )

    print("\n=== Result by task_type ===\n")
    print(header)
    print("-" * len(header))

    total_pass, total_fail = 0, 0

    for task_type in sorted(stats.keys()):
        p = stats[task_type]["PASS"]
        f = stats[task_type]["FAIL"]
        total = p + f
        acc = (p / total * 100) if total > 0 else 0

        print(
            f"{task_type.ljust(col_width)}"
            f"{p:>8}"
            f"{f:>8}"
            f"{total:>8}"
            f"{acc:>10.2f}"
        )

        total_pass += p
        total_fail += f

    total_all = total_pass + total_fail
    acc_all = (total_pass / total_all * 100) if total_all > 0 else 0

    print("-" * len(header))
    print(
        f"{'OVERALL'.ljust(col_width)}"
        f"{total_pass:>8}"
        f"{total_fail:>8}"
        f"{total_all:>8}"
        f"{acc_all:>10.2f}"
    )


if __name__ == "__main__":
    main()