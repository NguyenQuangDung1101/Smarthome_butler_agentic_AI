"""
check_tool_validity.py

Checks every tool name referenced in deterministic_eval fields:
  - ordering_constraints  (list of [tool_a, tool_b] pairs)
  - required_tool_calls   (list of tool names)
  - abandon_tool_calls    (list of tool names)

against the official tool names in tool_list.json.

Prints a summary of all invalid tool references grouped by test-case ID.
"""

import json
import os
import re

APPLIANCE_RE = re.compile(
    r"^appliance:\d+:(actuator|sensor):[a-zA-Z0-9_]+:(get|set)$"
)


def is_valid_name(name: str, valid_tools: set) -> bool:
    return name in valid_tools or bool(APPLIANCE_RE.match(name))


TOOL_LIST_PATH = os.path.join(os.path.dirname(__file__), "..", "tool_list.json")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_dataset_full.json")


def load_valid_tools(path: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        tools = json.load(f)
    return {t["name"] for t in tools}


def load_dataset(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_dataset(dataset: list[dict], valid_tools: set[str]) -> list[dict]:
    """
    Returns a list of violation dicts:
      {
        "id": str,
        "field": str,          # which field the bad tool was found in
        "invalid_tool": str,   # the offending tool name
        "context": str         # extra info (e.g. constraint pair)
      }
    """
    violations = []

    for tc in dataset:
        tc_id = tc.get("id", "<no id>")
        det_eval = tc.get("deterministic_eval", {})
        if not det_eval:
            continue

        # --- ordering_constraints ---
        for constraint in det_eval.get("ordering_constraints", []):
            for tool in constraint:
                if not is_valid_name(tool, valid_tools):
                    violations.append({
                        "id": tc_id,
                        "field": "ordering_constraints",
                        "invalid_tool": tool,
                        "context": f"constraint pair: {constraint}",
                    })

        # --- required_tool_calls ---
        for tool in det_eval.get("required_tool_calls", []):
            if not is_valid_name(tool, valid_tools):
                violations.append({
                    "id": tc_id,
                    "field": "required_tool_calls",
                    "invalid_tool": tool,
                    "context": "",
                })

        # --- abandon_tool_calls ---
        for tool in det_eval.get("abandon_tool_calls", []):
            if not is_valid_name(tool, valid_tools):
                violations.append({
                    "id": tc_id,
                    "field": "abandon_tool_calls",
                    "invalid_tool": tool,
                    "context": "",
                })

    return violations


TEMP_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "temp.json")


def main():
    print(f"Loading tool list from : {os.path.abspath(TOOL_LIST_PATH)}")
    valid_tools = load_valid_tools(TOOL_LIST_PATH)
    print(f"Valid tools ({len(valid_tools)}): {sorted(valid_tools)}\n")

    print(f"Loading dataset from   : {os.path.abspath(DATASET_PATH)}")
    dataset = load_dataset(DATASET_PATH)
    print(f"Total test cases       : {len(dataset)}\n")

    violations = check_dataset(dataset, valid_tools)

    if not violations:
        print("✓ All tool references in ordering_constraints, required_tool_calls, "
              "and abandon_tool_calls are valid.")
        return

    # Group by test-case ID
    grouped: dict[str, list[dict]] = {}
    for v in violations:
        grouped.setdefault(v["id"], []).append(v)

    print(f"✗ Found {len(violations)} invalid tool reference(s) across "
          f"{len(grouped)} test case(s):\n")
    print(f"{'ID':<12} {'Field':<25} {'Invalid Tool':<35} Context")
    print("-" * 100)
    for tc_id in sorted(grouped, key=lambda x: int(x.split("_")[1]) if "_" in x else x):
        for v in grouped[tc_id]:
            ctx = f"  [{v['context']}]" if v["context"] else ""
            print(f"{v['id']:<12} {v['field']:<25} {v['invalid_tool']:<35}{ctx}")

    # Unique invalid tool names summary
    unique_bad = sorted({v["invalid_tool"] for v in violations})
    print(f"\nUnique invalid tool names: {unique_bad}")

    # Build a lookup map: id -> full test case object
    tc_by_id = {tc.get("id"): tc for tc in dataset}

    # Collect one copy of each violating test case, preserving sorted order
    invalid_ids = sorted(grouped.keys(), key=lambda x: int(x.split("_")[1]) if "_" in x else x)
    output = [tc_by_id[tc_id] for tc_id in invalid_ids if tc_id in tc_by_id]

    with open(TEMP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(output)} test case(s) to: {os.path.abspath(TEMP_OUTPUT_PATH)}")


if __name__ == "__main__":
    main()
