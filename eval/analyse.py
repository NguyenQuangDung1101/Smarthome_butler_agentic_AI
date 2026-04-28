# import json

# SOURCE_FILE = "./eval/gemini-3-flash-preview-cloud/agent_output_gemini_0shot.json"
# TARGET_FILE = "./eval/agent_output_temp.json"
# OUTPUT_FILE = "./eval/agent_output_temp_updated.json"




# def main():
#     with open(SOURCE_FILE, "r", encoding="utf-8") as f:
#         source_data = json.load(f)

#     with open(TARGET_FILE, "r", encoding="utf-8") as f:
#         replace_data = json.load(f)

#     # Items in agent_output_temp.json will replace matching IDs in source
#     replace_map = {item["id"]: item for item in replace_data}

#     updated_data = []
#     replaced_count = 0

#     for item in source_data:
#         case_id = item["id"]

#         if case_id in replace_map:
#             updated_data.append(replace_map[case_id])
#             replaced_count += 1
#         else:
#             updated_data.append(item)

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(updated_data, f, indent=2, ensure_ascii=False)

#     print(f"Total source items: {len(source_data)}")
#     print(f"Total replacement items: {len(replace_data)}")
#     print(f"Total replaced: {replaced_count}")
#     print(f"Saved to: {OUTPUT_FILE}")


# if __name__ == "__main__":
#     main()






import json

SOURCE_FILE = "./eval/gemini-3-flash-preview-cloud/llm_judge_report_gemini_0shot.json"
TARGET_FILE = "./eval/llm_judge_report_temp.json"
OUTPUT_FILE = "./eval/llm_judge_report_updated.json"

def main():
    # 1. Load the source report
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        source_report = json.load(f)

    # 2. Load the target (replacement) data
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        target_data = json.load(f)
    
    # Handle if target_file is a full report object or just a list of results
    if isinstance(target_data, dict) and "results" in target_data:
        replace_list = target_data["results"]
    else:
        replace_list = target_data

    # Create a map for quick lookup: { "tc_01": {item_data} }
    replace_map = {item["id"]: item for item in replace_list}

    updated_results = []
    replaced_count = 0

    # 3. Replace matching items in the results list
    for item in source_report.get("results", []):
        case_id = item["id"]

        if case_id in replace_map:
            updated_results.append(replace_map[case_id])
            replaced_count += 1
        else:
            updated_results.append(item)

    # 4. Recalculate the Summary
    pass_count = sum(1 for item in updated_results if item.get("verdict") == "PASS")
    fail_count = sum(1 for item in updated_results if item.get("verdict") == "FAIL")
    
    new_summary = source_report.get("summary", {}).copy()
    new_summary["total_cases_evaluated"] = len(updated_results)
    new_summary["pass"] = pass_count
    new_summary["fail"] = fail_count

    # 5. Construct final object and save
    final_report = {
        "summary": new_summary,
        "results": updated_results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print(f"--- Process Complete ---")
    print(f"Total items in source:      {len(source_report.get('results', []))}")
    print(f"Items replaced:             {replaced_count}")
    print(f"New Summary Stats:          PASS: {pass_count}, FAIL: {fail_count}")
    print(f"Saved to:                   {OUTPUT_FILE}")

if __name__ == "__main__":
    main()








# import json

# EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
# AGENT_OUTPUT_FILE = "./eval/agent_output_qwen35_fewshot.json"
# OUTPUT_FILE = "./eval/temp.json"

# TARGET_STRING = "<final_answer>Inference failed after retries, no response.</final_answer>"


# def main():
#     with open(EVAL_DATASET_FILE, "r", encoding="utf-8") as f:
#         eval_data = json.load(f)

#     with open(AGENT_OUTPUT_FILE, "r", encoding="utf-8") as f:
#         agent_outputs = json.load(f)

#     # Collect failed IDs
#     failed_ids = set()
#     total_checked = 0

#     for item in agent_outputs:
#         if "inference_ouput" not in item:
#             continue

#         total_checked += 1
#         if TARGET_STRING in item["inference_ouput"]:
#             failed_ids.add(item["id"])

#     # Filter matching items from eval dataset
#     filtered = [item for item in eval_data if item["id"] in failed_ids]

#     # Save to temp.json
#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(filtered, f, indent=2, ensure_ascii=False)

#     # ---- Counts ----
#     print(f"Total agent outputs with inference_ouput: {total_checked}")
#     print(f"Total failed (matched string): {len(failed_ids)}")
#     print(f"Total copied to temp.json: {len(filtered)}")


# if __name__ == "__main__":
#     main()