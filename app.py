import json
import time
import threading
import os
import queue
import asyncio
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, request, Response

# Import from your existing files
from system import run_schedule_executor, run_update_appliance_status
from manual_control import control_appliance, device_mapping
from appliance_util import get_all_appliances_status
from espnode_manager.esp_communication import send_command
from session_manage import SessionManager

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

# Shared SessionManager for the web API (normal chat sessions)
sm = SessionManager()

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

# --- CHAT API ROUTES ---

@app.route('/api/chat/sessions', methods=['GET', 'POST'])
def chat_sessions():
    if request.method == 'GET':
        sessions = []
        for session_id, sess in sm.normal_session.items():
            agent = sess.get('agent')
            event_log = getattr(agent, 'event_log', [])
            first_user = next((e['content'] for e in event_log if e['type'] == 'user'), '')
            preview = (first_user[:55] + '…') if len(first_user) > 55 else first_user or 'New Chat'
            sessions.append({
                'id': session_id,
                'preview': preview,
                'message_count': len(event_log),
                'is_running': getattr(agent, 'is_running', False),
            })
        sessions.sort(key=lambda x: x['id'], reverse=True)
        return jsonify(sessions)
    else:  # POST
        data = request.json or {}
        model = data.get('model', 'gemini-3-flash-preview:cloud')
        session_id = sm.create_new_normal_session(model=model)
        return jsonify({'session_id': session_id})


@app.route('/api/chat/sessions/<string:session_id>/messages', methods=['GET'])
def get_chat_messages(session_id):
    """Return the full event log for a session."""
    session = sm.normal_session.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    agent = session['agent']
    return jsonify(getattr(agent, 'event_log', []))


@app.route('/api/chat/sessions/<string:session_id>/message', methods=['POST'])
def send_chat_message(session_id):
    """Send a user message and stream back SSE events as the agent reasons."""
    data = request.json or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    session = sm.normal_session.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    agent = session['agent']
    if agent.is_running:
        return jsonify({'error': 'Session is busy, please wait'}), 409

    q = queue.Queue()
    agent.stream_queue = q
    agent.is_running = True

    def run_agent():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(agent.run(user_message))
        except Exception as e:
            q.put({
                'type': 'error',
                'content': str(e),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
        finally:
            loop.close()
            agent.stream_queue = None
            agent.is_running = False
            q.put(None)  # sentinel – signals the generator to stop

    threading.Thread(target=run_agent, daemon=True).start()

    def generate():
        while True:
            event = q.get()
            if event is None:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, use_reloader=False) 
    # use_reloader=False is important so threads don't start twice