import json
import time
import threading
from flask import Flask, render_template, request, jsonify

# Import from your existing files
from system import run_schedule_executor
from manual_control import control_appliance, device_mapping
from appliance_util import get_all_appliances_status

app = Flask(__name__)

# --- BACKGROUND LOOPS ---
def loop_schedule_executor():
    """Loop 1: Runs the schedule executor"""
    print("Starting Schedule Executor Loop...")
    # run_schedule_executor()

def loop_appliance_status():
    """Loop 2: Continuously gets appliance status"""
    print("Starting Appliance Status Loop...")
    while True:
        try:
            # status = get_all_appliances_status()

            # You can log this to a file or just print it. 
            # We print a short indicator to avoid flooding the console too much.
            print(f"[Status Loop] Checked status. Length of status string: {len(status)}")
            time.sleep(10) # Check every 10 seconds
        except Exception as e:
            print(f"Error in status loop: {e}")
            time.sleep(10)

# Start threads before the first request
@app.before_request
def start_background_threads():
    if not hasattr(app, 'threads_started'):
        t1 = threading.Thread(target=loop_schedule_executor, daemon=True)
        t2 = threading.Thread(target=loop_appliance_status, daemon=True)
        t1.start()
        t2.start()
        app.threads_started = True

# --- WEB ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/appliances', methods=['GET'])
def get_appliances():
    """API for Tab 1: Fetch data from JSON file"""
    try:
        with open('appliances_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/device_mapping', methods=['GET'])
def get_mapping():
    """API to send the device mapping to the frontend for dropdowns"""
    return jsonify(device_mapping)

@app.route('/api/control', methods=['POST'])
def control():
    """API for Tab 2: Manual Control"""
    data = request.json
    espID = data.get('espID')
    device_name = data.get('device_name')
    value = data.get('value')

    if espID is None or device_name is None or value is None:
        return jsonify({"success": False, "error": "Missing parameters"})

    # 1. Use manual_control.py to generate the command payload
    command_payload = control_appliance(int(espID), device_name, value)
    
    if "error" in command_payload:
        return jsonify({"success": False, "error": command_payload["error"]})


if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, use_reloader=False) 
    # use_reloader=False is important so threads don't start twice