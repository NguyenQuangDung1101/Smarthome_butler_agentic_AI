import json
import time
import threading
import os
import queue
import asyncio
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, request, Response

# Import from your existing files
from loop_trigger import run_schedule_executor, run_update_appliance_status
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


# --- NOTES API ---

@app.route('/api/notes', methods=['GET'])
def get_notes():
    try:
        from tools import _load_notes
        return jsonify({"success": True, "data": _load_notes()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/notes', methods=['POST'])
def create_note():
    try:
        import uuid
        from tools import _load_notes, _save_notes
        data = request.json or {}
        text = data.get('text', '').strip()
        dates = data.get('dates', [])
        if not text or not dates:
            return jsonify({"success": False, "error": "text and dates are required"})
        notes = _load_notes()
        added = {}
        for date in dates:
            if date not in notes:
                notes[date] = {}
            note_id = uuid.uuid4().hex[:9]
            notes[date][note_id] = text
            added[date] = note_id
        _save_notes(notes)
        return jsonify({"success": True, "added": added})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    try:
        from tools import _load_notes, _save_notes
        data = request.json or {}
        new_text = data.get('text', '').strip()
        if not new_text:
            return jsonify({"success": False, "error": "text is required"})
        notes = _load_notes()
        for date_notes in notes.values():
            if note_id in date_notes:
                date_notes[note_id] = new_text
                _save_notes(notes)
                return jsonify({"success": True})
        return jsonify({"success": False, "error": "Note not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note_api(note_id):
    try:
        from tools import _load_notes, _save_notes
        notes = _load_notes()
        for date_key, date_notes in list(notes.items()):
            if note_id in date_notes:
                del date_notes[note_id]
                if not date_notes:
                    del notes[date_key]
                _save_notes(notes)
                return jsonify({"success": True})
        return jsonify({"success": False, "error": "Note not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# --- SCHEDULES API ---

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    try:
        with open('schedule_trigger.json', 'r', encoding='utf-8') as f:
            schedules = json.load(f)
        return jsonify({"success": True, "data": schedules})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/schedules', methods=['POST'])
def create_schedule():
    try:
        data = request.json or {}
        if 'datetime' not in data or 'appliance_control' not in data:
            return jsonify({"success": False, "error": "datetime and appliance_control are required"})
        ctrl = data['appliance_control']
        for field in ['espID', 'device_type', 'device_name', 'action', 'value']:
            if field not in ctrl:
                return jsonify({"success": False, "error": f"Missing appliance_control field: {field}"})
        try:
            datetime.strptime(data['datetime'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return jsonify({"success": False, "error": "datetime must be in format YYYY-MM-DD HH:MM:SS"})
        new_entry = {
            "datetime": data['datetime'],
            "appliance_control": ctrl,
            "executed": bool(data.get('executed', False))
        }
        with open('schedule_trigger.json', 'r', encoding='utf-8') as f:
            schedules = json.load(f)
        schedules.append(new_entry)
        with open('schedule_trigger.json', 'w', encoding='utf-8') as f:
            json.dump(schedules, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "index": len(schedules) - 1})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/schedules/<int:index>', methods=['PUT'])
def update_schedule(index):
    try:
        with open('schedule_trigger.json', 'r', encoding='utf-8') as f:
            schedules = json.load(f)
        if index < 0 or index >= len(schedules):
            return jsonify({"success": False, "error": "Index out of range"})
        data = request.json or {}
        if 'datetime' in data:
            try:
                datetime.strptime(data['datetime'], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return jsonify({"success": False, "error": "datetime must be in format YYYY-MM-DD HH:MM:SS"})
            schedules[index]['datetime'] = data['datetime']
        if 'appliance_control' in data:
            schedules[index]['appliance_control'] = data['appliance_control']
        if 'executed' in data:
            schedules[index]['executed'] = bool(data['executed'])
        with open('schedule_trigger.json', 'w', encoding='utf-8') as f:
            json.dump(schedules, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/schedules/<int:index>', methods=['DELETE'])
def delete_schedule(index):
    try:
        with open('schedule_trigger.json', 'r', encoding='utf-8') as f:
            schedules = json.load(f)
        if index < 0 or index >= len(schedules):
            return jsonify({"success": False, "error": "Index out of range"})
        schedules.pop(index)
        with open('schedule_trigger.json', 'w', encoding='utf-8') as f:
            json.dump(schedules, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# --- SCHEDULE SESSION LOOP API ---

@app.route('/api/schedule-loop/status', methods=['GET'])
def schedule_loop_status():
    thread_alive = sm._schedule_loop_thread.is_alive() if sm._schedule_loop_thread else False
    return jsonify({
        "running": sm.schedule_loop_running and thread_alive,
        "paused": sm.schedule_loop_paused,
        "thread_alive": thread_alive,
    })

@app.route('/api/schedule-loop/start', methods=['POST'])
def schedule_loop_start():
    started = sm.start_schedule_loop()
    return jsonify({"success": True, "started": started})

@app.route('/api/schedule-loop/stop', methods=['POST'])
def schedule_loop_stop():
    sm.stop_schedule_loop()
    return jsonify({"success": True})

@app.route('/api/schedule-loop/pause', methods=['POST'])
def schedule_loop_pause_toggle():
    sm.pause_schedule_loop()
    return jsonify({"success": True, "paused": sm.schedule_loop_paused})

@app.route('/api/schedule-loop/history', methods=['GET'])
def schedule_loop_history():
    history = []
    for infer_id, entry in sm.schedule_infer_history.items():
        history.append({
            "id": infer_id,
            "date_time": entry.get("date_time"),
            "session_id": entry.get("session_id"),
            "result": entry.get("result"),
            "user_context": entry.get("user_context"),
            "appliance_execute": entry.get("appliance_execute"),
            "moment": entry.get("moment"),
        })
    history.sort(key=lambda x: x.get("date_time", ""), reverse=True)
    return jsonify(history)

@app.route('/api/schedule-loop/permissions', methods=['GET'])
def schedule_loop_permissions():
    reqs = []
    for req_id, req in sm.permission_requests.items():
        reqs.append({
            "id": req["id"],
            "context": req["context"],
            "status": req["status"],
            "time": req["time"],
        })
    reqs.sort(key=lambda x: x.get("time", ""), reverse=True)
    return jsonify(reqs)

@app.route('/api/schedule-loop/permissions/<req_id>/respond', methods=['POST'])
def respond_permission(req_id):
    data = request.json or {}
    user_text = data.get("response", "").strip()
    ok = sm.respond_permission_request(req_id, user_text)
    if ok:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Request not found"}), 404

@app.route('/api/weekday-weekend', methods=['GET'])
def get_weekday_weekend():
    try:
        with open('./scheduler/weekday_weekend.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/weekday-weekend', methods=['PUT'])
def save_weekday_weekend():
    try:
        data = request.json
        if data is None:
            return jsonify({"success": False, "error": "No data provided"})
        # validate it's valid JSON structure
        json.dumps(data)
        with open('./scheduler/weekday_weekend.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# --- VOICE API ---
# Keyed by session_id: {"active": bool, "state": str, "stop_event": Event}
_voice_sessions: dict = {}


def _voice_loop(session_id: str, agent, stop_event):
    """Background thread: listen → STT → run agent → TTS → repeat."""
    from voice_function import listen_for_speech, speech_to_text, text_to_speech

    print(f"[VOICE] Loop started for session: {session_id}")
    while not stop_event.is_set():
        _voice_sessions[session_id]["state"] = "listening"
        try:
            audio = listen_for_speech(stop_event=stop_event)
        except Exception as e:
            print(f"[VOICE] listen_for_speech error: {e}")
            if stop_event.is_set():
                break
            time.sleep(1)
            continue

        if stop_event.is_set():
            break

        import numpy as np
        if not hasattr(audio, 'size') or audio.size == 0:
            continue

        _voice_sessions[session_id]["state"] = "transcribing"
        try:
            text = speech_to_text(audio)
        except Exception as e:
            print(f"[VOICE] STT error: {e}")
            continue

        if not text or stop_event.is_set():
            continue

        print(f"[VOICE] Heard: {text}")

        # Wait for agent to finish any ongoing inference
        _voice_sessions[session_id]["state"] = "waiting"
        while agent.is_running and not stop_event.is_set():
            time.sleep(0.5)

        if stop_event.is_set():
            break

        # Run agent
        _voice_sessions[session_id]["state"] = "processing"
        final = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            final = loop.run_until_complete(agent.run(text))
            loop.close()
        except Exception as e:
            print(f"[VOICE] Agent error: {e}")

        if stop_event.is_set():
            break

        if final:
            _voice_sessions[session_id]["state"] = "speaking"
            try:
                text_to_speech(final)
            except Exception as e:
                print(f"[VOICE] TTS error: {e}")

    _voice_sessions[session_id]["active"] = False
    _voice_sessions[session_id]["state"] = "idle"
    print(f"[VOICE] Loop stopped for session: {session_id}")


@app.route('/api/voice/start', methods=['POST'])
def voice_start():
    data = request.json or {}
    session_id = data.get('session_id', '').strip()
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    session = sm.normal_session.get(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404
    vs = _voice_sessions.get(session_id)
    if vs and vs.get("active"):
        return jsonify({"success": True, "already_active": True})
    agent = session["agent"]
    stop_event = threading.Event()
    _voice_sessions[session_id] = {"active": True, "state": "starting", "stop_event": stop_event}
    t = threading.Thread(target=_voice_loop, args=(session_id, agent, stop_event), daemon=True)
    t.start()
    return jsonify({"success": True})


@app.route('/api/voice/stop', methods=['POST'])
def voice_stop():
    data = request.json or {}
    session_id = data.get('session_id', '').strip()
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    vs = _voice_sessions.get(session_id)
    if not vs:
        return jsonify({"success": True, "was_active": False})
    vs.get("stop_event").set()
    _voice_sessions[session_id]["active"] = False
    _voice_sessions[session_id]["state"] = "stopping"
    return jsonify({"success": True})


@app.route('/api/voice/status/<string:session_id>', methods=['GET'])
def voice_status(session_id):
    vs = _voice_sessions.get(session_id)
    if not vs:
        return jsonify({"active": False, "state": "idle"})
    return jsonify({"active": vs.get("active", False), "state": vs.get("state", "idle")})


if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, use_reloader=False) 
    # use_reloader=False is important so threads don't start twice