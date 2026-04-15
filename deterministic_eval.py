
import re

# Extract to list of tool calls, appliance executions and final response returned
def extract_agent_actions(inference_output: str):
    pattern = re.compile(
        r'(<tool_call>.*?</tool_call>|<appliance>.*?</appliance>|<final_answer>.*?</final_answer>)',
        re.DOTALL
    )
    matches = pattern.findall(inference_output)
    results = [m.strip() for m in matches] # remove whitespace

    return results



if __name__ == "__main__":

    benchmark_path = "./eval/test_benchmark.json"
    output_path = "./eval/agent_output.json"