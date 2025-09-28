import os
import re
import json
import asyncio
from typing import Dict, Any, Optional, List
import logging
logger = logging.getLogger("OLLama")
logging.basicConfig(level=logging.INFO)
# Reuse your existing LLM + tools
from local_llm import Copilot
from tools_call import call_tool as async_call_tool  # your async tool dispatcher
from tools_call import TOOLS as TOOL_SPEC

# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────

TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
FINAL_ANSWER_RE = re.compile(r"<final_answer>\s*(.*?)\s*</final_answer>", re.DOTALL)
APPLIANCE_ANSWER_RE = re.compile(r"<appliance>\s*(.*?)\s*</appliance>", re.DOTALL)

def render_tools_contract(tool_spec: List[Dict[str, Any]]) -> str:
    lines = []
    for t in tool_spec:
        name = t.get("name", "")
        desc = t.get("description", "")
        schema = t.get("inputSchema", {})
        required = schema.get("required", [])
        props = schema.get("properties", {})
        lines.append(f"- name: {name}\n  description: {desc}\n  required: {required}\n  properties: {json.dumps(props, ensure_ascii=False)}")
    return "\n".join(lines)

def build_strong_system_prompt(user_system_prompt: str, tool_spec: List[Dict[str, Any]]) -> str:
    tools_doc = render_tools_contract(tool_spec)
    control = f"""
You can call tools using this EXACT format (one per line):

<tool_call>{{"name":"<tool_name>", "arguments":{{...}}}}</tool_call>

- Only output a tool call when you actually want me to execute it.
- After one or more tool calls, when you are ready to answer the user, output:

<final_answer>...your final answer for the user...</final_answer>

Available tools (schema):
{tools_doc}

Rules:
- Output ONLY either <tool_call>...</tool_call> or <final_answer>...</final_answer> at each step.
- Do NOT include extra commentary outside those tags.
- If a tool returns tabular data (CSV/text), read it and continue reasoning.
- If arguments are missing, request the needed info explicitly via <final_answer> asking the user.
"""
    return f"{user_system_prompt}\n\n{control}".strip()

async def call_tool_syncish(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Runs your async call_tool in a blocking-friendly way."""
    return await async_call_tool(name, arguments)

def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Find all <tool_call>{...}</tool_call> blocks and parse JSON."""
    calls = []
    for m in TOOL_CALL_RE.finditer(text):
        blob = m.group(1).strip()
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict) and "name" in obj:
                calls.append(obj)
        except Exception:
            # Skip malformed chunks; agent will ask LLM to retry
            pass
    return calls

def extract_final_answer(text: str) -> Optional[str]:
    m = FINAL_ANSWER_RE.search(text)
    return m.group(1).strip() if m else None

def extract_appliance_answer(text: str) -> Optional[str]:
    m = APPLIANCE_ANSWER_RE.search(text)
    return m.group(1).strip() if m else None

# ──────────────────────────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────────────────────────

class ToolCallingAgent:
    """
    Super-light agent loop:
    1) Provide system+tools contract + user message.
    2) Ask LLM for either tool calls or final answer.
    3) If tool calls found, execute and feed results back, then loop.
    4) Stop when final_answer is produced or when max_steps reached.
    """

    def __init__(self, llm: Copilot, system_prompt: str, max_steps: int = 6):
        self.llm = llm
        self.system_prompt = system_prompt
        self.step = 0
        self.max_steps = max_steps

        # Build conversation as a single growing prompt (since Copilot.infer takes plain text)
        self.conversation: List[str] = []

    def _compose_prompt(self) -> str:
        return "\n\n".join(self.conversation)

    def _append_user(self, text: str):
        self.conversation.append(f"[USER]\n{text}")

    def _append_system(self, text: str):
        self.conversation.append(f"[SYSTEM]\n{text}")

    def _append_agent(self, text: str):
        print(text)
        self.conversation.append(f"[AGENT]\n{text}")

    def _append_tool_result(self, name: str, result: Dict[str, Any]):
        # Your tools return {"content":[{"type":"text","text":"..."}]}
        # We flatten all text payloads.
        pieces = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                pieces.append(item.get("text", ""))
        payload = "\n".join(pieces).strip()
        safe = payload if payload else "<empty result>"
        print(f"[TOOL:{name}:RESULT]\n{safe}")
        self.conversation.append(f"[TOOL:{name}:RESULT]\n{safe}")

    async def run(self, user_prompt: str) -> str:
        # Step 0: seed system + user
        self._append_system(self.system_prompt)
        self._append_user(user_prompt)

        for step in range(1, self.max_steps + 1):
            self.step += 1
            self.conversation.append(f"\n[INFERENCE {self.step}]:\n")
            # 1) Ask LLM for the next action
            prompt_now = self._compose_prompt()
            llm_out = self.llm.infer(
                user_prompt=prompt_now,
                system_prompt="Follow the instructions precisely. Only output <tool_call>...</tool_call> or <appliance>...</appliance> or <final_answer>...</final_answer>."
            )
            if not llm_out:
                return "The LLM did not return a response."

            # 2) Check for final answer
            final = extract_final_answer(llm_out)
            if final is not None:
                return final

            appliance = extract_appliance_answer(llm_out)
            if appliance is not None:
                return appliance

            # 3) Parse tool calls (there can be multiple)
            calls = extract_tool_calls(llm_out)

            if not calls:
                # Ask the LLM to try again with stricter guidance
                self._append_agent("Your previous output didn't include a valid <tool_call> or <final_answer>. Please try again.")
                continue

            # 4) Execute tool(s) in order and append results
            for call in calls:
                name = call.get("name")
                args = call.get("arguments", {}) or {}
                self._append_agent(f"Executing tool: {name} with arguments: {json.dumps(args)}")

                try:
                    result = await call_tool_syncish(name, args)
                except Exception as e:
                    result = {"content":[{"type":"text","text": f"[agent] Tool '{name}' failed: {e}"}]}

                self._append_tool_result(name, result)

            # 5) After tool results are appended, loop back so LLM can continue / conclude

        # Safety exit
        return "Reached max reasoning steps without a <final_answer>. Please refine your request."

# ──────────────────────────────────────────────────────────────────────────────
# Example CLI usage
# ──────────────────────────────────────────────────────────────────────────────

def build_agent(system_prompt_text: str, model: str = "gemma3:4b", host: str = "http://localhost:11434") -> ToolCallingAgent:
    """
    Creates a ready-to-run agent with your tool schema injected into the system prompt.
    """
    llm = Copilot(host=host, model=model)
    sp = build_strong_system_prompt(system_prompt_text, TOOL_SPEC)
    return ToolCallingAgent(llm=llm, system_prompt=sp, max_steps=16)

def load_system_prompt(filename):
    try:
        with open(filename, 'r') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Error reading system prompt from file: {e}")
        return None

if __name__ == "__main__":
    # Your example system prompt
    role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
    instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

    parts = [role_sys_prompt, instruction_sys_prompt]
    sys_prompt = "\n\n".join([p for p in parts if p])

    # Start the agent
    agent = build_agent(sys_prompt, model="qwen3:1.7b")

    # Example user prompt; the LLM is expected to call tools in the right order.
    user_prompt = (
        "turn on the right light in the lobby, swtich the fan in bedroom to half power"
    )

    # What is the weather here at the current time (get the current date, current time, current location, get the weather information and check the relevant current time)"
    

    # Run it
    final = asyncio.run(agent.run(user_prompt))
    print("\n=== Final Answer ===\n")
    print(final)
