import json
import time
import threading
import os
from flask import Flask, send_from_directory, jsonify, request

# Import from your existing files
from system import run_schedule_executor, run_update_appliance_status
from manual_control import control_appliance, device_mapping
from appliance_util import get_all_appliances_status
from espnode_manager.esp_communication import send_command

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

# --- BACKGROUND LOOPS ---
def loop_schedule_executor():
    """Loop 1: Runs the schedule executor"""
    print("[SCHEDULE EXECUTOR]Starting Schedule Executor Loop...")
    run_schedule_executor()

def loop_appliance_status():
    """Loop 2: Continuously gets appliance status"""
    print("[STATUS LOOP] Appliance Status Loop...")
    run_update_appliance_status()


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
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

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

    result_message = send_command(command_payload, int(espID)-1)  # espID starts from 1, but our list is 0-indexed
    print("Command execution:", result_message)
    
        
    # Return success payload so the frontend knows it worked
    return jsonify({"success": True, "payload": command_payload})

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, use_reloader=False) 
    # use_reloader=False is important so threads don't start twice