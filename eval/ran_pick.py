import json
import math

INPUT_FILE = "eval_dataset_full.json"
OUTPUT_PREFIX = "eval_dataset_part"
NUM_SPLITS = 4


def main():
    # Load dataset
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of items")

    total = len(data)
    chunk_size = math.ceil(total / NUM_SPLITS)

    # Split and save
    for i in range(NUM_SPLITS):
        start = i * chunk_size
        end = start + chunk_size
        chunk = data[start:end]

        output_file = f"{OUTPUT_PREFIX}_{i+1}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunk, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(chunk)} items to {output_file}")


if __name__ == "__main__":
    main()