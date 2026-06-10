import os
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
logger = logging.getLogger("OLLama")
logging.basicConfig(level=logging.INFO)
# Reuse your existing LLM + tools
from local_llm import Copilot, load_system_prompt
from appliance_util import execute_appliance
from tools_call import call_tool as async_call_tool  # your async tool dispatcher
from tools_call import TOOLS as TOOL_SPEC
from tools import check_today_note

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
- If you need to execute house appliances, output:

<appliance>...json_config...</appliance>

- After one or multiple tool calls and appliances execution, when you are ready to answer the user, output:

<final_answer>...your final answer for the user...</final_answer>

Available tools (schema):
{tools_doc}

Rules:
- Output ONLY either <tool_call>...</tool_call>, <appliance>...</appliance>  or <final_answer>...</final_answer> at each step.
- Do NOT include extra commentary outside those tags (except thinking string, which is not be returned to user).
- You can call multiple tools in one response by outputting multiple <tool_call>...</tool_call>.
- If a tool returns tabular data (CSV/text), read it and continue reasoning.
- If house appliance execution return strange message, read it and continue reasoning.
- If the prompt lacks necessary arguments or clarity, you can request the missing information explicitly by using <final_answer> to ask the user to clarify the missing details or provide the required arguments.
"""
    return f"{user_system_prompt}\n\n{control}".strip()

def include_notes_to_prompt(base_prompt: str) -> str:
    today_notes = check_today_note()
    if not today_notes:
        return base_prompt
    note_section = "\n\n[TODAY NOTES] There are notes for today, please consider them when answering:\n"
    return base_prompt + note_section + "\n".join(f"- {note}" for note in today_notes)

async def call_tool_syncish(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return await async_call_tool(name, arguments)

def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls = []
    for m in TOOL_CALL_RE.finditer(text):
        blob = m.group(1).strip()
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict) and "name" in obj:
                calls.append(obj)
        except Exception:
            pass
    return calls

def extract_appliance_answer(text: str) -> Optional[str]:
    m = APPLIANCE_ANSWER_RE.search(text)
    return m.group(1).strip() if m else None

def extract_final_answer(text: str) -> Optional[str]:
    m = FINAL_ANSWER_RE.search(text)
    return m.group(1).strip() if m else None

# ──────────────────────────────────────────────────────────────────────────────
# Agent (multi-turn capable)
# ──────────────────────────────────────────────────────────────────────────────

class ToolCallingAgent:
    def __init__(self, llm: Copilot, system_prompt: str, max_steps: int = 6, max_history: int = 10):
        self.llm = llm
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.max_history = max_history + 1  # total [INFERENCE] blocks to retain across all turns
        self.user_turn = 0
        self.turn_step = 0  # resets per user turn
        self.conversation: List[str] = []
        self.first_comunicate = True
        self.latest_appliance_execution = {}
        self.latest_final = {}
        self.conversation_sunmmary = None
        self.conversation_sunmmary_updated = False
        # Web chat support
        self.event_log: List[Dict] = []
        self.stream_queue = None  # set to a queue.Queue() for SSE streaming
        self.is_running = False

    # ──────────────────────────────────────────────────────────────────────────────
    # Helper functions
    # ──────────────────────────────────────────────────────────────────────────────

    def _log_event(self, event_type: str, content: str, extra: Optional[Dict] = None):
        """Record an event in event_log and optionally stream it via stream_queue - chat history in frontend"""
        event = {
            "type": event_type,
            "content": content,
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        if extra:
            event.update(extra)
        self.event_log.append(event)
        if self.stream_queue is not None:
            self.stream_queue.put(event)

    def _compose_prompt(self) -> str:
        return "\n".join(self.conversation)

    def _append_user(self, text: str):
        self.user_turn += 1
        self.turn_step = 0
        self.conversation.append(f"\n[USER {self.user_turn}]\n{text}")
        self._trim_history_multi()

    def _append_agent(self, text: str):
        self.conversation.append(f"[AGENT]\n{text}")
        self._trim_history_multi()

    def _append_final(self, text: str):
        self.conversation.append(f"[Final for user {self.user_turn}]\n{text}")
        self._trim_history_multi()

    def _append_tool_result(self, name: str, result: Dict[str, Any]):
        pieces = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                pieces.append(item.get("text", ""))
        payload = "\n".join(pieces).strip()
        safe = payload if payload else "<empty result>"
        # print(f"[TOOL:{name}:RESULT]\n{safe}\n")
        self._log_event("tool_result", safe, {"tool_name": name})
        self.conversation.append(f"[TOOL:{name}:RESULT]\n{safe}")
        self._trim_history_multi()

    def _count_inference_blocks(self) -> int:
        count = 0
        for item in self.conversation:
            s = item.lstrip()
            if s.startswith("[INFERENCE "):
                count += 1
        return count

    def _trim_history_multi(self):
        while self._count_inference_blocks() > self.max_history:
            N = len(self.conversation)
            start_idx = None
            for idx, item in enumerate(self.conversation):
                s = item.lstrip()
                if s.startswith("[INFERENCE "):
                    start_idx = idx
                    break
            if start_idx is None:
                return
            end_idx = N
            for j in range(start_idx + 1, N):
                sj = self.conversation[j].lstrip()
                if sj.startswith("[INFERENCE ") or sj.startswith("[USER "):
                    end_idx = j
                    break
            del self.conversation[start_idx:end_idx]

    def update_conversation_summary(self):
        curr_conversation = self._compose_prompt()
        self.conversation_sunmmary = self.llm.infer(
            user_prompt=curr_conversation,
            system_prompt="[SYSTEM]\nSummarize the conversation concisely, focusing on key points and briefly note the decisions made. Do not use icons"
        )
        self.conversation_sunmmary_updated = True
    
    def get_conversation_summary(self):
        if not self.conversation_sunmmary_updated or not self.conversation_sunmmary:
            self.update_conversation_summary()
        return self.conversation_sunmmary

    # ──────────────────────────────────────────────────────────────────────────────
    # Inference function
    # ──────────────────────────────────────────────────────────────────────────────

    async def step_once(self) -> Optional[str]:
        self.conversation_sunmmary_updated = False
        self.turn_step += 1
        self.conversation.append(f"\n[INFERENCE {self.turn_step}]:\n")
        self._trim_history_multi()

        prompt_now = self._compose_prompt()
        # print(prompt_now)
        llm_out = self.llm.infer(
            user_prompt=prompt_now,
            system_prompt=(
                "[SYSTEM]\nFollow the instructions precisely. Only output "
                "<tool_call>...</tool_call>, <appliance>...</appliance> or <final_answer>...</final_answer>.\n"
                "<final_answer> must be a standalone response, mutually exclusive with <tool_call> and <appliance> and should not be call at the same time (in an inference response) with <tool_call> and <appliance>.\n"
                f"{self.system_prompt}"
            )
        )
        # print(f"[LLM OUTPUT]:\n{llm_out}\n")
        if not llm_out:
            self._append_agent("The LLM did not return a response.")
            return None

        self._append_agent(f"LLM output: {llm_out}")

        check_appliance = True
        appliance = extract_appliance_answer(llm_out)
        if appliance is not None:
            self._append_agent(f"Execute appliance: {appliance}")
            try:
                formated, log_to_save = execute_appliance(appliance)
                # print(f"[APPLIANCE EXECUTION RESULT]:\n{formated}\n")
                result = f"Appliance executed successfully{log_to_save}"
                check_appliance = False
                self._log_event("appliance", formated, {"appliance_config": appliance})
                self.latest_appliance_execution = {
                    "execution": appliance,
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
            except Exception as e:
                result = f"Appliance execution failed: {e}"
            self._append_agent(result)

        calls = extract_tool_calls(llm_out)
        if calls:
            for call in calls:
                name = call.get("name")
                args = call.get("arguments", {}) or {}
                self._append_agent(f"Executing tool: {name} with arguments: {json.dumps(args)}")
                try:
                    result = await call_tool_syncish(name, args)
                except Exception as e:
                    result = {"content":[{"type":"text","text": f"[agent] Tool '{name}' failed: {e}"}]}
                self._append_tool_result(name, result)

        if check_appliance:
            self._append_agent("No appliance setting was applied")        

        final = extract_final_answer(llm_out)
        if not any([appliance, calls, final]):
            self._append_agent("Your previous output didn't include a valid <tool_call>...</tool_call>, <appliance>...</appliance>, or <final_answer>...</final_answer>. This will be considered as thinking string. Please try again.")
            return None

        if final is not None:
            self._append_final(final)
            self.latest_final = {
                "final": final,
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            self._log_event("final", final)
            return final

        return None

    async def run(self, user_prompt: str, use_kb=False, kb_path="./kb_store/test1") -> str:
        self.first_comunicate = False
        self._log_event("user", user_prompt)
        self._append_user(user_prompt)
        for _ in range(1, self.max_steps + 1):
            final = await self.step_once()
            self._trim_history_multi()
            if final is not None:
                return final
        return "Reached max reasoning steps without a <final_answer>. Please refine your request."
    
    async def eval_collect(self, user_prompt: str, use_kb=False, kb_path="./kb_store/test1") -> str:
        self.first_comunicate = False
        self._log_event("user", user_prompt)
        self._append_user(user_prompt)
        for _ in range(1, self.max_steps + 1):
            final = await self.step_once()
            self._trim_history_multi()
            if final is not None:
                return self._compose_prompt()
        return self._compose_prompt() + "\n\nReached max reasoning steps without a <final_answer>. Please refine your request."

    async def chat_cli(self, first_user_prompt=None):
        self.first_comunicate = False
        check_first_prompt = True if first_user_prompt else False
        print("Interactive mode. After each step, press Enter to continue reasoning or type a new prompt to start a new turn.\n")
        while True:
            try:
                if first_user_prompt and check_first_prompt:
                    user_text = first_user_prompt
                    check_first_prompt = False
                else:
                    user_text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return
            if not user_text:
                continue
            if user_text.lower() == "exit()":
                print("Bye.")
                return
            self._append_user(user_text)
            i = 0
            while True:
                i += 1
                final = await self.step_once()
                self._trim_history_multi()
                if final is not None:
                    print("\n=== Final Answer ===\n")
                    print(final)
                    break
                try:
                    if i >= self.max_steps:
                        print("Reached max reasoning steps without a <final_answer>. Please refine your request.")
                        i = 0
                    follow = input("(Enter=continue to answer the current prompt, or type a new prompt): ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    return
                if follow == "":
                    continue
                elif follow == "exit()":
                    print("Bye.")
                    return
                else:
                    self._append_user(follow)
                    continue

# ──────────────────────────────────────────────────────────────────────────────
# Example CLI usage
# ──────────────────────────────────────────────────────────────────────────────

def build_agent(system_prompt_text: str, model: str = "gemma4:31b-cloud", host: str = "http://localhost:11434") -> ToolCallingAgent:
    llm = Copilot(host=host, model=model)
    sp = build_strong_system_prompt(system_prompt_text, TOOL_SPEC)
    sp = include_notes_to_prompt(sp)
    return ToolCallingAgent(llm=llm, system_prompt=sp, max_steps=20, max_history=13)


if __name__ == "__main__":
    # role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
    # instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

    # parts = [role_sys_prompt, instruction_sys_prompt]
    # sys_prompt = "\n\n".join([p for p in parts if p])
    # agent = build_agent(sys_prompt, model="gpt-oss:20b-cloud")

    # # Interactive multi-turn terminal chat:
    # asyncio.run(agent.chat_cli())


    a = '<appliance>[{"espID": 3, "device_type": "actuator", "device_name": "led2", "action": "set", "value": true}, {"espID": 3, "device_type": "actuator", "device_name": "servo", "action": "set", "value": false}]</appliance> <final_answer>All scheduled actions have been set: bed light turned on and bedroom door unlocked. Let me know if anything else needs adjustment.</final_answer>'
    appliance = extract_appliance_answer(a)
    print(appliance)
    print(extract_final_answer(a))

    
    # What is the weather here at the current time (get the current date, current time, current location, get the weather information and check the relevant current time)"
    # turn on the left in the hallway, switch the fan in bedroom to half power

    # user_prompt = "check the current time, if it is later than 02:00pm, turn the bedroom light off and turn the bed light on, if ealier then turn the livingroom light on and set living room fan to 78%, if the current weather is raining then set all fan to 50, but if the current weather is not raining then set every fan in the house to 100%"
    # final = asyncio.run(agent.run(user_prompt))
    # print("\n=== Final Answer ===\n")
    # print(final)


    