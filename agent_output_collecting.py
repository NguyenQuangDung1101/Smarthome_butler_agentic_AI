import json
import os
from datetime import datetime
from tools import add_note
from espnode_manager.esp_communication import send_command
from local_llm import load_system_prompt
from agent import build_agent
import asyncio



def clear_file(path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

def clear_json_files() -> None:
    clear_file("./schedule_trigger.json")
    clear_file("./note_storage.json")







def collect_agent_outputs(benchmark_path: str, output_path: str = "agent_output.json") -> None:
    # Clear schedule_trigger and note_storage before running the benchmark
    clear_json_files()

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark = json.load(f)

    # Initialize output file
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            if not isinstance(results, list):
                results = []
        except Exception:
            results = []
    else:
        results = []

    for case in benchmark:
        print("[START COLLECTING]: "+ case["id"])
        result_item = {
            "id": case["id"]
        }
        try:
            # Set up preconditions - Notes
            if case.get("preconditions", {}).get("notes_setup", []):
                for note in case["preconditions"]["notes_setup"]:
                    if note["date"].lower() == "today":
                        add_note(note["note_text"], [datetime.now().strftime('%Y-%m-%d')])
                    else:
                        add_note(note["note_text"], [note["date"]])
            
            # Set up preconditions - Appliance states
            if case.get("preconditions", {}).get("state_setup", []):
                for command in case["preconditions"]["state_setup"]:
                    send_command(command, command["espID"] - 1)


            role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
            instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

            parts = [role_sys_prompt, instruction_sys_prompt]
            sys_prompt = "\n\n".join([p for p in parts if p])
            agent = build_agent(sys_prompt, model="gemini-3-flash-preview:cloud")

            inference_ouput = asyncio.run(agent.eval_collect(case["prompt"]))

            result_item["inference_ouput"] = inference_ouput

        except Exception as e:
            result_item["error"] = str(e)

        results.append(result_item)

        # Save after each case
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print("[FINISH]")







if __name__ == "__main__":

    
    benchmark_path = "./eval/test_benchmark.json"
    collect_agent_outputs(benchmark_path)