import asyncio
import threading
import uuid
from datetime import datetime
from local_llm import load_system_prompt
from agent import build_agent
from appliance_util import get_all_appliances_status
import json
import time

# gpt-oss:20b-cloud
# gpt-oss:120b-cloud
# models/gemini-2.5-flash-lite
# gemini-3-flash-preview:cloud
# qwen3.5:397b-cloud
# qwen3-vl:235b-cloud
# gemma4:31b-cloud

class SessionManager:
    def __init__(self):
        self.normal_session = {}
        self.schedule_session = {}
        self.schedule_infer_history = {}
        self.moment_cache = [] # moment checking history
        # Schedule loop control
        self.schedule_loop_running = False
        self.schedule_loop_paused = False
        self._schedule_loop_thread = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially
        # Permission requests: req_id -> {id, context, response, status, time, _event}
        self.permission_requests = {}

    def get_list_of_normal_session(self):
        return list(self.normal_session.keys())
    
    def get_list_of_schedule_session(self):
        return list(self.schedule_session.keys())

    def get_list_of_schedule_infer_history(self):
        return list(self.schedule_infer_history.keys())

    def append_context_question(self, prompt="", context_text=None):
        if not context_text:
            return None
        return prompt + "\n\n[ASKING USER]:" + context_text

    def get_latest_schedule_infer_history(self):
        latest = None
        latest_time = None

        for infer_id, entry in self.schedule_infer_history.items():
            dt_str = entry.get("date_time", infer_id)
            try:
                t = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if latest_time is None or t > latest_time:
                latest_time = t
                latest = {
                    "date_time": dt_str,
                    "session_id": entry.get("session_id"),
                    "result": entry.get("result"),
                    "appliance_execute": entry.get("appliance_execute")
                }

        return latest

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

    def get_latest_final_by_agent_normal(self):
        latest = None
        latest_time = None

        for session_id, sess in self.normal_session.items():
            agent = sess.get("agent")
            if not agent:
                continue
            lf = getattr(agent, "latest_final", None)
            if not lf or "time" not in lf:
                continue
            try:
                t = datetime.strptime(lf["time"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if latest_time is None or t > latest_time:
                latest_time = t
                latest = {
                    "final": lf.get("final"),
                    "time": lf.get("time"),
                    "session_id": session_id
                }

        return latest

    def get_latest_convesation_summary_by_agent_normal(self):
        latest = None
        latest_time = None
        latest_agent = None

        for session_id, sess in self.normal_session.items():
            agent = sess.get("agent")
            if not agent:
                continue
            lf = getattr(agent, "latest_final", None)
            if not lf or "time" not in lf:
                continue
            try:
                t = datetime.strptime(lf["time"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if latest_time is None or t > latest_time:
                latest_time = t
                latest_agent = agent
        if latest_agent:
            latest = latest_agent.get_conversation_summary()

        return latest

    #################################################################################################
    def create_new_normal_session(self, model="gemma4:31b-cloud", context_text=None):
        print("[NORMAL INFER] Creating new normal session...")
        role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
        instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

        parts = [role_sys_prompt, instruction_sys_prompt]
        sys_prompt = "\n\n".join([p for p in parts if p])

        agent = build_agent(sys_prompt, model=model)
        session_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.normal_session[session_id] = {
            "agent": agent,
            "context_text": context_text
        }
        return session_id
    
    def infer_normal_session(self, session_id=None, context_text=None):
        if not session_id:
            print(f"[NORMAL INFER] Did not receive session ID.")
            session_id = self.create_new_normal_session(context_text=context_text)
        else:
            session = self.normal_session.get(session_id)
            if not session:
                print(f"[NORMAL INFER] Session ID {session_id} not found.")
                session_id = self.create_new_normal_session(context_text=context_text)

        session = self.normal_session.get(session_id)
        agent = session["agent"]
        context_text = session["context_text"]
        
        print(f"[NORMAL INFER] Running agent session ID: {session_id}")
        user_prompt = self.append_context_question(context_text=context_text)
        asyncio.run(agent.chat_cli(first_user_prompt=user_prompt))
    
    ###############################################################################################
    def create_new_schedule_session(self, model="gemma4:31b-cloud", context_text=None):
        print("[SCHEDULE INFER] Creating new schedule session...")
        role_sys_prompt = load_system_prompt('./system_prompt_doc/role.txt')
        instruction_sys_prompt = load_system_prompt('./system_prompt_doc/instruction.txt')

        parts = [role_sys_prompt, instruction_sys_prompt]
        sys_prompt = "\n\n".join([p for p in parts if p])

        try:
            sys_prompt += f"\n\n[CURRENT APPLIANCES STATUS]:\n{get_all_appliances_status()}"
        except:
            sys_prompt += f"\n\n[CURRENT APPLIANCES STATUS]:\nFailed to get appliances status."

        if self.get_latest_appliance_execution_by_agent():
            sys_prompt += f"\n\n[LATEST APPLIANCE EXECUTION BY AGENT]: {self.get_latest_appliance_execution_by_agent()['time']}\n{self.get_latest_appliance_execution_by_agent()['execution']}"

        if self.get_latest_schedule_infer_history():
            sys_prompt += f"\n\n[LATEST SCHEDULE INFER HISTORY]: {self.get_latest_schedule_infer_history()}"
        
        # if self.get_latest_final_by_agent_normal():
        #     sys_prompt += f"\n\n[LATEST FINAL RESPONSE BY AGENT IN NORMAL SESSION]: {self.get_latest_final_by_agent_normal()['time']}\n{self.get_latest_final_by_agent_normal()['final']}"

        latest_summary = self.get_latest_convesation_summary_by_agent_normal()
        # print(f"Latest summary: {latest_summary}")
        if latest_summary:
            sys_prompt += f"\n\n[LATEST CONVERSATION SUMMARY BY AGENT IN NORMAL SESSION]:\n{latest_summary}"

        agent = build_agent(sys_prompt, model=model)
        session_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.schedule_session[session_id] = {
            "agent": agent,
            "context_text": context_text
        }

        return session_id
        
    def infer_schedule_session(self, session_id=None, context_text=None, user_prompt="None", schedule_infer_id=datetime.now().strftime('%Y-%m-%d %H:%M:%S')):
        input_context = context_text  # save before session overwrite
        if not session_id:
            print(f"[SCHEDULE INFER] Did not receive session ID.")
            session_id = self.create_new_schedule_session(context_text=context_text)
        else:
            session = self.schedule_session.get(session_id)
            if not session:
                print(f"[SCHEDULE INFER] Session ID {session_id} not found.")
                session_id = self.create_new_schedule_session(context_text=context_text)

        session = self.schedule_session.get(session_id)
        agent = session["agent"]
        context_text = session["context_text"]

        user_prompt = self.append_context_question(user_prompt, context_text) if context_text else user_prompt
        
        print(f"[SCHEDULE INFER] Running agent session ID: {session_id} with schedule_infer_id: {schedule_infer_id}")
        # print(user_prompt)
        if context_text:
            asyncio.run(agent.chat_cli(first_user_prompt=user_prompt))
            final = getattr(agent, "latest_final", None)["final"] if getattr(agent, "latest_final", None) else None
        else:
            final = asyncio.run(agent.run(user_prompt))
            print("\n=== Final Answer ===\n")
            print(final)
            
        self.schedule_infer_history[schedule_infer_id] = {
            "date_time": schedule_infer_id,
            "session_id": session_id,
            "result": final,
            "user_context": input_context,
            "appliance_execute": getattr(agent, "latest_appliance_execution", None),
        }
        # print(self.schedule_infer_history[schedule_infer_id])

    # ── Schedule loop control ──────────────────────────────────────────────────

    def start_schedule_loop(self, scheduler_file="./scheduler/weekday_weekend.json"):
        if self._schedule_loop_thread and self._schedule_loop_thread.is_alive():
            return False  # already running
        self.schedule_loop_running = True
        self.schedule_loop_paused = False
        self._pause_event.set()
        self._schedule_loop_thread = threading.Thread(
            target=self.schedule_session_loop,
            args=(scheduler_file,),
            daemon=True
        )
        self._schedule_loop_thread.start()
        return True

    def stop_schedule_loop(self):
        self.schedule_loop_running = False
        self._pause_event.set()  # unblock if paused so thread can exit

    def pause_schedule_loop(self):
        if not self.schedule_loop_paused:
            self.schedule_loop_paused = True
            self._pause_event.clear()
        else:
            self.schedule_loop_paused = False
            self._pause_event.set()

    def _request_permission(self, context_text):
        """Block the schedule loop thread until the user responds via the web UI."""
        req_id = uuid.uuid4().hex[:8]
        evt = threading.Event()
        self.permission_requests[req_id] = {
            "id": req_id,
            "context": context_text,
            "response": None,
            "status": "pending",
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "_event": evt
        }
        print(f"[SCHEDULE INFER - PERMISSION REQUEST] {req_id}: waiting for user response...")
        evt.wait(timeout=300)  # wait up to 5 minutes
        req = self.permission_requests[req_id]
        if req.get("status") != "responded":
            req["status"] = "timeout"
        return req.get("response") or ""

    def respond_permission_request(self, req_id, user_text):
        if req_id not in self.permission_requests:
            return False
        req = self.permission_requests[req_id]
        req["response"] = user_text
        req["status"] = "responded"
        evt = req.get("_event")
        if evt:
            evt.set()
        return True

    #################################################################################################

    def schedule_session_loop(self, scheduler_file="./scheduler/weekday_weekend.json"):
        self.schedule_loop_running = True
        while self.schedule_loop_running:
            self._pause_event.wait()  # blocks while paused
            if not self.schedule_loop_running:
                break
            print("[SCHEDULE SESSION LOOP] Checking schedule moments...")
            schedule_infer_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # schedule_infer_id = "2025-11-17 07:31:06"
            current_moment = self.get_moment(schedule_infer_id, scheduler_file)
            if not current_moment:
                user_prompt = f"It is {schedule_infer_id}, no event or execution reached.\nPlease provide your suggestions or have a general check of the house appliances system and take action if necessary."
                self.infer_schedule_session(user_prompt=user_prompt, schedule_infer_id=schedule_infer_id)
                self.schedule_infer_history[schedule_infer_id].update({"moment": "No moment reached."})
            elif current_moment.get('schedule_check', None) == "init":
                # Init
                user_prompt = f"It is {schedule_infer_id}, too early and have not reached any events or execution yet.\nHave a general check of the house appliances system and compare it with the initial settings below:\n{json.dumps(current_moment['moment']['data'], indent=2)}\nPlease provide your suggestions or actions to ensure the appliances are set up correctly."
                self.infer_schedule_session(user_prompt=user_prompt, schedule_infer_id=schedule_infer_id)
                self.schedule_infer_history[schedule_infer_id].update({"moment": f"Init moment:\n{json.dumps(current_moment['moment']['data'], indent=2)}"})
            else:
                # Not init
                if "appliance_setting" not in f"{current_moment.get('moment', None)}":
                    user_prompt = f"It is {schedule_infer_id}, here is owner's activity period:\n{json.dumps(current_moment['moment'], indent=2)}\nHave a general check of the house appliances system to ensure the appliances are set up correctly according to the owner's activity, take action if necessary."
                    self.infer_schedule_session(user_prompt=user_prompt, schedule_infer_id=schedule_infer_id)
                    self.schedule_infer_history[schedule_infer_id].update({"moment": f"Moment:\n{json.dumps(current_moment['moment'], indent=2)}"})
                else:
                    context_text = None
                    for item in current_moment['moment']:
                        if item['type'] == 'appliance_setting' and 'Ask for user permission before execute' in item['data'].get('note', ''):
                            context_text = f"{context_text}\n{item['data'].get('appliances', '')}"
                    
                    if context_text:
                        context_text = "Some appliance settings require user permission before execution. Please confirm the following appliances to be set:" + context_text
                        user_text = self._request_permission(context_text)
                        context_text = f"{context_text}\n\n[User confirmation]: {user_text}"

                    user_prompt = f"It is {schedule_infer_id}, here is some of the moment may have reached:\n{json.dumps(current_moment['moment'], indent=2)}\nPlease have a check on the house appliances system and take action to set up the appliances accordingly."
                    # print(user_prompt)
                    self.infer_schedule_session(user_prompt=user_prompt, context_text=context_text, schedule_infer_id=schedule_infer_id)
                    self.schedule_infer_history[schedule_infer_id].update({"moment": f"Moment:\n{json.dumps(current_moment['moment'], indent=2)}"})

            # interruptible sleep so stop_schedule_loop takes effect quickly
            deadline = time.time() + 30
            while time.time() < deadline and self.schedule_loop_running:
                self._pause_event.wait()
                time.sleep(1)
        self.schedule_loop_running = False


    def get_moment(self, datetime_str = None, schedule_file="./scheduler/weekday_weekend.json"):
        if datetime_str is None:
            datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # parsing
        current_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        current_date = current_dt.strftime('%Y-%m-%d')
        current_time = current_dt.strftime('%H:%M:%S')
        current_day = current_dt.strftime('%A')
        
        with open(schedule_file, 'r') as f:
            schedule_data = json.load(f)
        
        # weekday/weekend
        schedule_type = None
        if current_day in schedule_data['schedule']['weekday']['applicable_days']:
            schedule_type = 'weekday'
        elif current_day in schedule_data['schedule']['weekend']['applicable_days']:
            schedule_type = 'weekend'
        else:
            return None
        
        schedule = schedule_data['schedule'][schedule_type]
        
        # Check if current date is already in moment_cache
        today_cache = [entry for entry in self.moment_cache if entry['date'] == current_date]
        
        # init?
        first_moment_time = None
        
        # first moment
        all_times = []
        if schedule['appliance_setting']:
            all_times.extend([s['time'] for s in schedule['appliance_setting']])
        if schedule['owner_activity']:
            for activity in schedule['owner_activity']:
                if 'time' in activity:
                    all_times.append(activity['time'])
                elif 'time_period' in activity:
                    all_times.append(activity['time_period']['start'])
        
        if all_times:
            first_moment_time = min(all_times)
        
        if first_moment_time and current_time < first_moment_time:
            result = {
                'schedule_type': schedule_type,
                'schedule_check': "init",
                'moment': {
                    'type': 'initial_settings',
                    'data': schedule['initial_settings']
                }
            }
            
            self.moment_cache.append({
                'date': current_date,
                'time': current_time,
                'datetime': datetime_str,
                'moment': result
            })
            
            return result
        
        matching_moments = []
        
        # appliance_setting moments
        for setting in schedule['appliance_setting']:
            setting_time = setting['time']
            
            # check 1st time
            time_cached = any(
                (isinstance(entry.get('moment'), dict) and 
                isinstance(entry.get('moment', {}).get('moment'), dict) and
                entry.get('moment', {}).get('moment', {}).get('type') == 'appliance_setting' and
                entry.get('moment', {}).get('moment', {}).get('data', {}).get('time') == setting_time) or
                (isinstance(entry.get('moment'), dict) and 
                isinstance(entry.get('moment', {}).get('moment'), list) and 
                any(m.get('type') == 'appliance_setting' and m.get('data', {}).get('time') == setting_time 
                    for m in entry.get('moment', {}).get('moment', [])))
                for entry in today_cache
            )

            setting_dt = datetime.strptime(f"{current_date} {setting_time}", '%Y-%m-%d %H:%M:%S')
            time_diff_minutes = (current_dt - setting_dt).total_seconds() / 60
            
            if current_time >= setting_time and not time_cached and time_diff_minutes <= 15:
                matching_moments.append({
                    'type': 'appliance_setting',
                    'data': setting
                })
        
        # owner_activity
        for activity in schedule['owner_activity']:
            # time
            if 'time' in activity:
                activity_time = activity['time']
                time_cached = any(
                    (isinstance(entry.get('moment'), dict) and 
                    isinstance(entry.get('moment', {}).get('moment'), dict) and
                    entry.get('moment', {}).get('moment', {}).get('type') == 'owner_activity' and
                    entry.get('moment', {}).get('moment', {}).get('data', {}).get('time') == activity_time) or
                    (isinstance(entry.get('moment'), dict) and 
                    isinstance(entry.get('moment', {}).get('moment'), list) and 
                    any(m.get('type') == 'owner_activity' and m.get('data', {}).get('time') == activity_time 
                        for m in entry.get('moment', {}).get('moment', [])))
                    for entry in today_cache
                )
                
                # Calculate time difference in minutes
                activity_dt = datetime.strptime(f"{current_date} {activity_time}", '%Y-%m-%d %H:%M:%S')
                time_diff_minutes = (current_dt - activity_dt).total_seconds() / 60
                
                if current_time >= activity_time and not time_cached and time_diff_minutes <= 15:
                    matching_moments.append({
                        'type': 'owner_activity',
                        'data': activity
                    })
            
            # time_period
            if 'time_period' in activity:
                start_time = activity['time_period']['start']
                end_time = activity['time_period']['end']
                
                if start_time <= current_time <= end_time:
                    matching_moments.append({
                        'type': 'owner_activity_period',
                        'data': activity
                    })

        if matching_moments:
            result = {
                'schedule_type': schedule_type,
                'schedule_check': "not_init",
                'moment': matching_moments
            }
            
            self.moment_cache.append({
                'date': current_date,
                'time': current_time,
                'datetime': datetime_str,
                'moment': result
            })
            return result
        
        return None
    #################################################################################################





if __name__ == "__main__":

    test = SessionManager()
    # print(json.dumps(test.get_moment("2025-10-31 01:30:01")['moment']['data'], indent=2))
    # print("###############################")
    # if not test.get_moment("2025-10-31 07:20:05"):
    #     print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
    # print("###############################")
    # print(test.get_moment("2025-10-31 06:35:06"))
    # print("###############################")
    # print(test.get_moment("2025-10-31 09:30:06"))
    test.infer_normal_session()
    # test.schedule_session_loop()
    # test.infer_normal_session()
    # test.create_new_schedule_session()
    # {'execution': '[{"espID": 1, "device_type": "actuator", "device_name": "led1", "action": "set", "value": true}]', 'time': '2025-10-25 15:49:51', 'session_id': '2025-10-25 15:49:34', 'session_type': 'normal'}