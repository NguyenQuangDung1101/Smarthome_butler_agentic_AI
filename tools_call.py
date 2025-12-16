import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import subprocess
import platform
from typing import Any, Dict
from tools import get_current_datetime, get_hourly_forecast, get_current_location, search_and_read_web_link

# ── LOAD TOOLS DEFINITION FROM JSON ──────────────────────────────────────
TOOLS_JSON_PATH = os.path.join(os.path.dirname(__file__), "tool_list.json")
with open(TOOLS_JSON_PATH, "r", encoding="utf-8") as f:
    TOOLS = json.load(f)

# ── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────
# ---- NEW TOOL WRAPPERS ---------------------------------------------------
def tool_get_current_datetime(arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        text = get_current_datetime()
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error in get_current_datetime: {e}"}]}

def tool_get_hourly_forecast(arguments: Dict[str, Any]) -> Dict[str, Any]:
    current_location = arguments.get("current_location", False)
    latitude = arguments.get("latitude", None)
    longitude = arguments.get("longitude", None)
    date = arguments.get("date", "")
    if date == "":
        return "Can not get date from arguments"
    try:
        text = get_hourly_forecast(current_location, latitude, longitude, date)
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error in get_hourly_forecast: {e}"}]}

def tool_get_current_location(arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        text = get_current_location()
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error in get_current_location: {e}"}]}

def tool_search_and_read_web_link(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query", "")
    num_results = arguments.get("num_results", 1)
    read = arguments.get("read", True)
    try:
        text = search_and_read_web_link(query, num_results, read)
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error in search_and_read_web_link: {e}"}]}



# ── TOOL DISPATCH MAP ────────────────────────────────────────────────────
TOOL_DISPATCH = {
    "get_current_datetime": tool_get_current_datetime,
    "get_hourly_forecast": tool_get_hourly_forecast,
    "get_current_location": tool_get_current_location,
    "search_and_read_web_link": tool_search_and_read_web_link,
}

# ── PUBLIC ENTRYPOINT (kept async signature) ─────────────────────────────
async def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    # Use function mapping; keep minimal if for unknown tool
    func = TOOL_DISPATCH.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}")
    return func(arguments)
