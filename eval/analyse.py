import json

EVAL_DATASET_FILE = "./eval/eval_dataset_full.json"
AGENT_OUTPUT_FILE = "./eval/agent_output_qwen35_fewshot.json"
OUTPUT_FILE = "./eval/temp.json"

TARGET_STRING = "<final_answer>Inference failed after retries, no response.</final_answer>"


def main():
    with open(EVAL_DATASET_FILE, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    with open(AGENT_OUTPUT_FILE, "r", encoding="utf-8") as f:
        agent_outputs = json.load(f)

    # Collect failed IDs
    failed_ids = set()
    for item in agent_outputs:
        if "inference_ouput" not in item:
            continue  # skip items without this field

        inference_output = item["inference_ouput"]
        if TARGET_STRING in inference_output:
            failed_ids.add(item["id"])

    # Filter matching items from eval dataset
    filtered = [item for item in eval_data if item["id"] in failed_ids]

    # Save to temp.json
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()