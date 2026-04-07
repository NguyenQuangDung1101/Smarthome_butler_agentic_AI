import json
from collections import Counter

# Load the dataset
file_path = './eval/eval_dataset.json'

try:
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Extract all task types
    task_types = [item.get('task_type') for item in data]

    # Count occurrences
    stats = Counter(task_types)
    total_tasks = len(data)

    # Print Statistics
    print(f"{'Task Type':<25} | {'Count':<5} | {'Percentage':<10}")
    print("-" * 45)
    
    # Sort by count descending
    for task, count in stats.most_common():
        percentage = (count / total_tasks) * 100
        print(f"{task:<25} | {count:<5} | {percentage:>8.2f}%")

    print("-" * 45)
    print(f"{'Total':<25} | {total_tasks:<5} | 100.00%")

except FileNotFoundError:
    print(f"Error: {file_path} not found.")
except json.JSONDecodeError:
    print("Error: Failed to decode JSON.")