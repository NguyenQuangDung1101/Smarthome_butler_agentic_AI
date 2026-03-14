import json
import time
import os
from datetime import datetime
from appliance_util import execute_appliance, get_all_appliances_status
from session_manage import SessionManager

DELAY_TRIGGER_RANGE = 30  # seconds
FREQUENCY_CHECK_SCHEDULE = 15  # seconds


# Frequency of checking the schedule_trigger (by agent) file and executing appliances is set to 15 seconds.
def run_schedule_executor():
    schedule_file = "schedule_trigger.json"
    print("[SCHEDULE EXECUTOR] Starting schedule executor loop...")

    while True:
        now = datetime.now()

        if not os.path.exists(schedule_file):
            time.sleep(FREQUENCY_CHECK_SCHEDULE)
            continue

        try:
            with open(schedule_file, "r", encoding="utf-8") as f:
                schedules = json.load(f)

            if not isinstance(schedules, list):
                schedules = []

        except Exception:
            time.sleep(FREQUENCY_CHECK_SCHEDULE)
            continue

        updated = False

        for item in schedules:
            try:
                if item.get("executed") is True:
                    continue

                schedule_time = datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S")
                diff = (now - schedule_time).total_seconds()

                # trigger window: gap between now and schedule_time is between 0 and DELAY_TRIGGER_RANGE seconds
                if 0 <= diff <= DELAY_TRIGGER_RANGE:
                    try:
                        formated,_ = execute_appliance(f"[{json.dumps(item["appliance_control"])}]")    # must be a list
                        print(f"[APPLIANCE EXECUTION RESULT]:\n{formated}\n")

                        item["executed"] = True
                        updated = True
                    except Exception as e:
                        print(f"Appliance execution failed: {e}")

            except Exception:
                continue

        if updated:
            with open(schedule_file, "w", encoding="utf-8") as f:
                json.dump(schedules, f, ensure_ascii=False, indent=2)

        time.sleep(FREQUENCY_CHECK_SCHEDULE)

def run_update_appliance_status():
    while True:
        print(["[STATUS LOOP] Checking appliance status..."])
        try:
            status = get_all_appliances_status()
            print(f"[Status Loop] Checked status. Length of status string: {len(status)}")
            time.sleep(FREQUENCY_CHECK_SCHEDULE)
        except Exception as e:
            print(f"Error in status loop: {e}")
            time.sleep(FREQUENCY_CHECK_SCHEDULE)



if __name__ == "__main__":

    # while True:
    #     get_all_appliances_status()
    #     # reset tab



    run_schedule_executor()

    # session_manager = SessionManager()
    # session_manager.schedule_session_loop()

    # # chat tab
    # if new_chat:
    #     new_chat1 = SessionManager()
    #     new_chat1.infer_normal_session()

    # # Start the schedule executor in a separate thread or process
    # import threading
    # executor_thread = threading.Thread(target=run_schedule_executor, daemon=True)
    # executor_thread.start()

    # # Start the main session manager loop
    # session_manager = SessionManager()
    # session_manager.schedule_session_loop()
