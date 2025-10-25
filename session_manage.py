import asyncio
from datetime import datetime
from local_llm import load_system_prompt
from agent import build_agent
from appliance_util import get_all_appliances_status


class SessionManager:
    def __init__(self):
        self.normal_session = {}
        self.schedule_session = {}
        self.schedule_session_history = {}

    def get_list_of_normal_session(self):
        return list(self.normal_session.keys())
    
    def get_list_of_schedule_session(self):
        return list(self.schedule_session.keys())

    def append_context_question(self, sys_prompt, context_text):
        return sys_prompt + "\n\n[ASKING USER]" + context_text

    def get_latest_appliance_execution_by_agent(self):
        latest = None
        latest_time = None

        for session_type, sessions in (("normal", self.normal_session), ("schedule", self.schedule_session)):
            for session_id, sess in sessions.items():
                agent = sess.get("agent")
                if not agent:
                    continue
                lae = getattr(agent, "latest_appliance_execution", None)
                if not lae or "time" not in lae:
                    continue
                try:
                    t = datetime.strptime(lae["time"], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                if latest_time is None or t > latest_time:
                    latest_time = t
                    latest = {
                        "execution": lae.get("execution"),
                        "time": lae.get("time"),
                        "session_id": session_id,
                        "session_type": session_type,
                    }

        return latest

    #################################################################################################
    def create_new_normal_session(self, model="gpt-oss:20b-cloud"):
        print("Creating new normal session...")
        role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
        instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

        parts = [role_sys_prompt, instruction_sys_prompt]
        sys_prompt = "\n\n".join([p for p in parts if p])

        agent = build_agent(sys_prompt, model=model)
        session_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.normal_session[session_id] = {
            "agent": agent,
            "context_text": None
        }
        return session_id
    
    def infer_normal_session(self, session_id=None):
        if not session_id:
            print(f"Did not receive session ID.")
            session_id = self.create_new_normal_session()
        else:
            session = self.normal_session.get(session_id)
            if not session:
                print(f"Session ID {session_id} not found.")
                session_id = self.create_new_normal_session()

        session = self.normal_session.get(session_id)
        agent = session["agent"]
        context_text = session["context_text"]
        
        print(f"Running agent session ID: {session_id}")
        asyncio.run(agent.chat_cli())
    
    #################################################################################################
    def create_new_schedule_session(self, model="gpt-oss:20b-cloud", context_text=None):
        print("Creating new normal session...")
        role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
        instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

        parts = [role_sys_prompt, instruction_sys_prompt]
        sys_prompt = "\n\n".join([p for p in parts if p])

        sys_prompt += f"\n\n[CURRENT APPLIANCES STATUS]:\n{get_all_appliances_status()}"

        if self.get_latest_appliance_execution_by_agent():
            sys_prompt += f"\n\n[LATEST APPLIANCE EXECUTION BY AGENT]: {self.get_latest_appliance_execution_by_agent()['time']}\n{self.get_latest_appliance_execution_by_agent()['execution']}"

        print(sys_prompt)




        agent = build_agent(sys_prompt, model=model)
        session_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.normal_session[session_id] = {
            "agent": agent,
            "context_text": context_text
        }
        return session_id
        

    #################################################################################################

if __name__ == "__main__":
    # role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
    # instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

    # parts = [role_sys_prompt, instruction_sys_prompt]
    # sys_prompt = "\n\n".join([p for p in parts if p])

    # #gpt-oss:20b-cloud
    # #qwen3:1.7b
    # agent = build_agent(sys_prompt, model="gpt-oss:20b-cloud")

    # # Interactive multi-turn terminal chat:
    # asyncio.run(agent.chat_cli())

    test = SessionManager()
    test.infer_normal_session()
    test.create_new_schedule_session()
    # {'execution': '[{"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "set", "value": true}]', 'time': '2025-10-25 15:49:51', 'session_id': '2025-10-25 15:49:34', 'session_type': 'normal'}