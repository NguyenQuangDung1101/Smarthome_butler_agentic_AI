from datetime import datetime
import pandas as pd
import requests
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, Optional
from bs4 import BeautifulSoup
import re
import os
import uuid
from local_llm import load_system_prompt
from local_llm import Copilot

# --------------------------------------------------------
# -------------- DATE, TIME, WEATHER TOOL ----------------
# --------------------------------------------------------

def get_current_datetime():
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    weekday_str = now.strftime('%A')
    
    output = f"Current date: {date_str} - Day: {weekday_str} - Current time: {time_str}"
    return output

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle (light)",
    57: "Freezing drizzle (dense)",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain (light)",
    67: "Freezing rain (heavy)",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm (slight/moderate)",
    96: "Thunderstorm with hail (slight)",
    99: "Thunderstorm with hail (heavy)",
}

def get_hourly_forecast(current_location, latitude, longitude, date: str) -> str:
    if not date:
        return "Date parameter is required"
    if current_location:
        latitude, longitude, city, country = get_current_location(True)
        noti = f"Get weather forecast for current location: {city}, {country}:\n"
    elif latitude and longitude:
        noti = f"Get weather forecast for specified coordinates: Latitude {latitude}, Longitude {longitude}:\n"
    else:
        latitude, longitude, city, country = get_current_location(True)
        noti = f"Longitude or latitude information are missing\nReturn current location: {city}, {country}:\n"

    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&hourly=temperature_2m,relative_humidity_2m,windspeed_10m,weathercode,cloudcover"
        f"&forecast_days=7&timezone=auto"
    )
    forecast_response = requests.get(forecast_url)
    if forecast_response.status_code != 200:
        return f"Forecast request failed: {forecast_response.status_code}"
    data = forecast_response.json()

    df = pd.DataFrame({
        "Time": data["hourly"]["time"],
        "temperature (°C)": data["hourly"]["temperature_2m"],
        "Humidity (%)": data["hourly"]["relative_humidity_2m"],
        "Windspeed (m/s)": data["hourly"]["windspeed_10m"],
        "weathercode": data["hourly"]["weathercode"],
        "Cloudcover (%)": data["hourly"]["cloudcover"]
    })
    df["Time"] = pd.to_datetime(df["Time"]).dt.strftime("%H:%M:%S")
    df["date"] = pd.to_datetime(data["hourly"]["time"]).date.astype(str)

    df["Weather"] = df["weathercode"].map(WEATHER_CODES).fillna("Unknown")
    df = df.drop(columns=["weathercode"])
    
    if date in set(df["date"]):
        result_df = df[df["date"] == date].drop(columns=["date"])
        return f"{noti}Weather forecast in {date}:\n{result_df.to_csv(index=False)}"
    else:
        return f"{noti}Date {date} not available in forecast range"


def get_current_location(return_value = False):
    response = requests.get("https://ipinfo.io/json")
    if response.status_code == 200:
        data = response.json()
        lat, lon = map(float, data["loc"].split(","))
        if return_value:
            return lat, lon, data.get('city'), data.get('country')
        return f"Current location:\nLatitude: {lat}, Longitude: {lon}, city: {data.get('city')}, country: {data.get('country')}"
    else:
        return "Failed to get location"



# --------------------------------------------------------
# ------------------- SEARCHING TOOL ---------------------
# --------------------------------------------------------
# dung:d74c53982d4259c26022ca3e2a0c66d78e43e424057fb9dfa165cb93652b5164
# hieu:6a5e2ee6d9d2f509e1d70af4f6a0b524fec1af4018b40afceade9ac98b2e4c92
# banoi:5c5ac81171d4c6129e4269a141a02f05b40f5b109de42c5ff647380f635f102d
# me:23691d22fce3f90644c0b155310271745a725e91a1a232d728f6afdbcd2f7d27

def search_and_read_web_link(
    query: str,
    num_results: int = 3,
    read: bool = True,
    api_key: Optional[str] = "23691d22fce3f90644c0b155310271745a725e91a1a232d728f6afdbcd2f7d27",
    timeout: int = 15
) -> List[Dict[str, Any]]:
    """
    Search using SerpAPI and optionally fetch text from result links.
    Returns a list of dicts: {'title','link','snippet','content'} where 'content' is None or short extracted text.
    """
    api_key = api_key or os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise ValueError("SerpAPI key required. Set SERPAPI_API_KEY env or pass api_key.")
    params = {
        "engine": "google",
        "q": query,
        "num": num_results,
        "api_key": api_key,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"SerpAPI request failed: {resp.status_code} - {resp.text}")
    data = resp.json()
    organic = data.get("organic_results", [])  # list of results
    results: List[Dict[str, Any]] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible)"}
    for item in organic[:num_results]:
        title = item.get("title")
        link = item.get("link") or item.get("displayed_link")
        snippet = item.get("snippet") or item.get("snippet")  # fallback
        content = None
        if read and link:
            try:
                r2 = requests.get(link, timeout=timeout, headers=headers)
                if r2.status_code == 200 and "text" in r2.headers.get("Content-Type", ""):
                    soup = BeautifulSoup(r2.text, "html.parser")
                    text = " ".join(soup.stripped_strings)
                    # truncate to reasonable length
                    if len(text) > 7000:
                        text = text[:7000] + " ... [truncated]"
                    content = text
                else:
                    content = f"Unable to read content (status {r2.status_code})"
            except Exception as e:
                content = f"Failed to fetch/read: {e}"
        results.append({"title": title, "link": link, "snippet": snippet, "content": content})

    llm = Copilot(host="http://localhost:11434", model="gpt-oss:20b-cloud")
    summary_search_results = llm.infer(
        user_prompt = f"Retrieved data for the query: '{query}'. Here are the search results:\n{json.dumps(results, indent=2)}\n\nPlease provide a concise summary of the key information relevant to the query.(return full information in detail if the query is asking for specific information)",
        system_prompt = "You will receive search results from the internet (may from multiple different sources). Summarize the key information relevant to the query in a concise manner.",
    )
    sum_append_link = "Links to the sources:\n"
    for item in results:
        sum_append_link += f"Link: {item["link"]} - Title: {item["title"]}\n"

    # return results
    return f"{sum_append_link}Sumary:\n{summary_search_results}"



# --------------------------------------------------------
# -------------------- NOTING TOOL -----------------------
# --------------------------------------------------------

NOTE_STORAGE_PATH = Path(__file__).parent / "note_storage.json"

def _load_notes() -> dict:
    if not NOTE_STORAGE_PATH.exists() or NOTE_STORAGE_PATH.stat().st_size == 0:
        return {}
    with open(NOTE_STORAGE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_today_note() -> str:
    now = datetime.now().strftime('%Y-%m-%d')
    notes = _load_notes()
    if now not in notes or not notes[now]:
        return None
    return list(notes[now].values())

def _save_notes(notes: dict) -> None:
    with open(NOTE_STORAGE_PATH, 'w', encoding='utf-8') as f:
        json.dump(notes, f, indent=4, ensure_ascii=False)


def add_note(note_text: str, dates: list) -> str:
    notes = _load_notes()
    note_id_list = []

    
    added_dates = []
    for date in dates:
        if date not in notes:
            notes[date] = {}
        note_id = uuid.uuid4().hex[:9]
        note_id_list.append(note_id)
        notes[date][note_id] = note_text
        added_dates.append(date)
    
    _save_notes(notes)
    return f"Note added successfully with ID: {note_id_list} to dates: {', '.join(added_dates)}"

def read_note(date: str = None, id: str = None) -> str:
    notes = _load_notes()
    results = []
    
    if id:
        found = False
        for date_key, date_notes in notes.items():
            if id in date_notes:
                results.append(f"Note ID {id} (Date: {date_key}):\n{date_notes[id]}")
                found = True
                break
        if not found:
            results.append(f"Note with ID {id} not found.")
    
    if date:
        if date not in notes:
            results.append(f"No notes found for date {date}.")
        else:
            date_notes = notes[date]
            if not date_notes:
                results.append(f"No notes found for date {date}.")
            else:
                result = f"Notes for {date}:\n"
                for note_id, note_text in date_notes.items():
                    result += f"- ID {note_id}: {note_text}\n"
                results.append(result)
    
    if not results:
        return "Please provide either date or id parameter."
    
    return "\n\n".join(results)

def check_note(date: str) -> str:
    notes = _load_notes()
    
    if date not in notes:
        return f"No notes for date {date}."
    
    count = len(notes[date])
    if count == 0:
        return f"No notes for date {date}."
    
    note_ids = list(notes[date].keys())
    ids_list = "\n".join([f"- {note_id}" for note_id in note_ids])
    
    return f"{count} note(s) found for date {date}.\nNote IDs:\n{ids_list}"

def delete_note(id: str) -> str:
    notes = _load_notes()
    
    found = False
    date_to_delete = None
    
    for date_key, date_notes in notes.items():
        if id in date_notes:
            del date_notes[id]
            found = True
            if len(date_notes) == 0:
                date_to_delete = date_key
            break
    
    if not found:
        return f"Note with ID {id} not found."
    
    if date_to_delete:
        del notes[date_to_delete]
    
    _save_notes(notes)
    return f"Note with ID {id} deleted successfully."



# --------------------------------------------------------
# ------------- SCHEDULE TRIGGER AGENT TOOL --------------
# --------------------------------------------------------
def trigger_schedule_agent(request_info: str) -> str:

    role_sys_prompt = load_system_prompt('./system_prompt_doc/tool_schedule_trigger_role.txt')
    instruction_sys_prompt = load_system_prompt('./system_prompt_doc/tool_schedule_trigger_instruction.txt')

    parts = [f"Current date and time: {get_current_datetime()}", role_sys_prompt, instruction_sys_prompt]
    sys_prompt = "\n\n".join([p for p in parts if p])

    llm = Copilot(host="http://localhost:11434", model="gpt-oss:20b-cloud")

    def _extract_json(text: str):
        text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        code_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if code_match:
            return json.loads(code_match.group(1))

        obj_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if obj_match:
            return json.loads(obj_match.group(1))

        raise ValueError("LLM output does not contain valid JSON")

    def _normalize_datetime(dt_str: str):
        if not isinstance(dt_str, str):
            return dt_str

        dt_str = dt_str.strip()

        # correct: YYYY-MM-DD HH:MM:SS
        try:
            datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return dt_str
        except Exception:
            pass

        # fix: YYYY-MM-DDHH:MM:SS -> YYYY-MM-DD HH:MM:SS
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})$", dt_str)
        if m:
            fixed = f"{m.group(1)} {m.group(2)}"
            try:
                datetime.strptime(fixed, "%Y-%m-%d %H:%M:%S")
                return fixed
            except Exception:
                pass

        # fix: YYYY/MM/DD HH:MM:SS -> YYYY-MM-DD HH:MM:SS
        m = re.match(r"^(\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2}:\d{2})$", dt_str)
        if m:
            fixed = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
            try:
                datetime.strptime(fixed, "%Y-%m-%d %H:%M:%S")
                return fixed
            except Exception:
                pass

        # fix ISO: YYYY-MM-DDTHH:MM:SS -> YYYY-MM-DD HH:MM:SS
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T](\d{2}:\d{2}:\d{2})$", dt_str)
        if m:
            fixed = f"{m.group(1)} {m.group(2)}"
            try:
                datetime.strptime(fixed, "%Y-%m-%d %H:%M:%S")
                return fixed
            except Exception:
                pass

        return dt_str

    def _validate_output(data):
        valid_devices = {
            (1, "actuator", "led1"): "bool",
            (1, "actuator", "motor1"): "int",
            (2, "actuator", "led1"): "bool",
            (2, "actuator", "led2"): "bool",
            (2, "actuator", "motor1"): "int",
            (2, "actuator", "motor2"): "int",
            (3, "actuator", "led1"): "bool",
            (3, "actuator", "led2"): "bool",
            (3, "actuator", "led3"): "bool",
            (3, "actuator", "motor1"): "int",
            (3, "actuator", "motor2"): "int",
            (3, "actuator", "servo"): "bool",
            (3, "actuator", "pump"): "bool",
        }

        def _validate_control(ctrl):
            required = ["espID", "device_type", "device_name", "action"]
            for k in required:
                if k not in ctrl:
                    return False, f"Missing field in appliance_control: {k}"

            key = (ctrl["espID"], ctrl["device_type"], ctrl["device_name"])
            if key not in valid_devices:
                return False, f"Invalid device mapping: {key}"

            if ctrl["device_type"] != "actuator":
                return False, "Only actuator schedule is supported"

            if ctrl["action"] != "set":
                return False, "Scheduled appliance action must be 'set'"

            if "value" not in ctrl:
                return False, "Missing value for actuator set action"

            expected_type = valid_devices[key]
            value = ctrl["value"]

            if expected_type == "bool":
                if not isinstance(value, bool):
                    return False, f"Value for {key} must be boolean"
            elif expected_type == "int":
                if not isinstance(value, int):
                    return False, f"Value for {key} must be integer"
                if not (0 <= value <= 100):
                    return False, f"Value for {key} must be in range 0-100"

            return True, None

        def _validate_schedule_item(item):
            if not isinstance(item, dict):
                return False, "Each schedule item must be an object"

            if "datetime" not in item:
                return False, "Missing datetime"

            if "appliance_control" not in item:
                return False, "Missing appliance_control"

            item["datetime"] = _normalize_datetime(item["datetime"])

            try:
                datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return False, "datetime must be in format YYYY-MM-DD HH:MM:SS"

            return _validate_control(item["appliance_control"])

        schedules = None

        if isinstance(data, list):
            schedules = data
        elif isinstance(data, dict):
            if "schedules" in data and isinstance(data["schedules"], list):
                schedules = data["schedules"]
            elif "datetime" in data and "appliance_control" in data:
                schedules = [data]
            else:
                return False, "JSON format is invalid for schedule tool", None
        else:
            return False, "Output must be a JSON object or array", None

        if len(schedules) == 0:
            return False, "Schedule list is empty", None

        for idx, item in enumerate(schedules):
            ok, err = _validate_schedule_item(item)
            if not ok:
                return False, f"Schedule item #{idx + 1} invalid: {err}", None

        return True, None, schedules

    def _save_schedules(schedules):
        file_path = "schedule_trigger.json"

        # ensure each schedule has executed flag
        for s in schedules:
            s["executed"] = False

        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        else:
            existing = []

        existing.extend(schedules)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    last_error = None
    last_raw_output = None

    for attempt in range(3):
        if attempt == 0:
            user_prompt = request_info
        else:
            user_prompt = (
                f"{request_info}\n\n"
                f"Previous output was invalid: {last_error}\n"
                f"Please regenerate strictly valid JSON only.\n"
                f"Datetime format must be exactly YYYY-MM-DD HH:MM:SS.\n"
                f"Validation passed: false"
            )

        schedule_strigger = llm.infer(
            user_prompt=user_prompt,
            system_prompt=sys_prompt,
        )
        # print(schedule_strigger)

        last_raw_output = schedule_strigger

        try:
            parsed = _extract_json(schedule_strigger)
            ok, err, schedules = _validate_output(parsed)

            if ok:
                _save_schedules(schedules)
                return json.dumps(
                    {
                        "status": "success",
                        "message": "Schedule saved successfully",
                        "data": schedules
                    },
                    ensure_ascii=False
                )

            last_error = err

        except Exception as e:
            last_error = str(e)

    return json.dumps(
        {
            "status": "error",
            "message": f"Failed to generate valid schedule after retries: {last_error}",
            "raw_output": last_raw_output
        },
        ensure_ascii=False
    )



if __name__ == "__main__":
    # print(get_current_datetime())
    # print(get_current_location())
    # print(get_hourly_forecast(False, None, 108.2068, "2025-12-20"))
    # print(check_today_note())
    trigger_schedule_agent("I am going to sleep in the bedroom for about 1 minute, please turn on the fan and turn off the light (just when i sleep only, do reverse after that)")

    # res = serp_search_and_read("today news in viet nam", num_results=3, read=True)
    # print(res)