import json
from collections import defaultdict

EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
REPORT_FILE = r"C:\Users\quang\Desktop\Research\smart_house\eval\gemini-3-flash-preview-cloud-0shot\deterministic_report_gemini_0shot.json"
output = r"C:\Users\quang\Desktop\Research\smart_house\eval\gemini-3-flash-preview-cloud-0shot\agent_output_gemini_0shot.json"

def main():
    with open(EVAL_DATASET_FILE, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    with open(output, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    id_to_exec_time = {
        item["id"]: item["execution_time"]
        for item in output_data
        if "id" in item and "execution_time" in item
    }

    id_to_task_type = {item["id"]: item["task_type"] for item in eval_data}

    stats = defaultdict(lambda: {"PASS": 0, "FAIL": 0})
    exec_times = defaultdict(list)

    for result in report_data["results"]:
        case_id = result["id"]
        outcome = result["result"]

        if case_id not in id_to_task_type:
            continue

        stats[id_to_task_type[case_id]][outcome] += 1

    for item in eval_data:
        case_id = item["id"]
        task_type = item["task_type"]
        if case_id in id_to_exec_time:
            exec_times[task_type].append(id_to_exec_time[case_id])

    # ---- Dynamic column width ----
    max_task_len = max(len(t) for t in stats.keys())
    col_width = max(max_task_len, len("Task Type")) + 2

    header = (
        f"{'Task Type'.ljust(col_width)}"
        f"{'PASS':>8}"
        f"{'FAIL':>8}"
        f"{'TOTAL':>8}"
        f"{'ACC (%)':>10}"
        f"{'AVG TIME (s)':>14}"
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
        times = exec_times.get(task_type, [])
        avg_time = sum(times) / len(times) if times else 0

        print(
            f"{task_type.ljust(col_width)}"
            f"{p:>8}"
            f"{f:>8}"
            f"{total:>8}"
            f"{acc:>10.2f}"
            f"{avg_time:>14.2f}"
        )

        total_pass += p
        total_fail += f

    total_all = total_pass + total_fail
    acc_all = (total_pass / total_all * 100) if total_all > 0 else 0
    all_times = [t for times in exec_times.values() for t in times]
    overall_avg = sum(all_times) / len(all_times) if all_times else 0

    print("-" * len(header))
    print(
        f"{'OVERALL'.ljust(col_width)}"
        f"{total_pass:>8}"
        f"{total_fail:>8}"
        f"{total_all:>8}"
        f"{acc_all:>10.2f}"
        f"{overall_avg:>14.2f}"
    )

    # ---- Average execution time by task_type ----
    with open(output, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    id_to_exec_time = {
        item["id"]: item["execution_time"]
        for item in output_data
        if "id" in item and "execution_time" in item
    }

    exec_times = defaultdict(list)
    for item in eval_data:
        case_id = item["id"]
        task_type = item["task_type"]
        if case_id in id_to_exec_time:
            exec_times[task_type].append(id_to_exec_time[case_id])

    time_header = (
        f"{'Task Type'.ljust(col_width)}"
        f"{'COUNT':>8}"
        f"{'AVG TIME (s)':>14}"
    )

    print("\n=== Average Execution Time by task_type ===\n")
    print(time_header)
    print("-" * len(time_header))

    total_times = []
    for task_type in sorted(exec_times.keys()):
        times = exec_times[task_type]
        avg = sum(times) / len(times)
        total_times.extend(times)
        print(
            f"{task_type.ljust(col_width)}"
            f"{len(times):>8}"
            f"{avg:>14.2f}"
        )

    overall_avg = sum(total_times) / len(total_times) if total_times else 0
    print("-" * len(time_header))
    print(
        f"{'OVERALL'.ljust(col_width)}"
        f"{len(total_times):>8}"
        f"{overall_avg:>14.2f}"
    )


if __name__ == "__main__":
    main()