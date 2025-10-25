import pandas as pd
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union



# --------------------------------------------------------
# ------------------- APPLIANCE TOOL----------------------
# --------------------------------------------------------

_APPLIANCES_FILE = Path("appliances_data.json")
Number = Union[int, float]

def _check_constraint(val: Any, c: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (ok, msg). msg empty if ok, else reason."""
    t = c.get("type")
    if t == "boolean":
        if isinstance(val, bool):
            return True, ""
        return False, "expected boolean"
    if t == "integer":
        if not isinstance(val, int):
            return False, "expected integer"
        mn, mx = c.get("min"), c.get("max")
        if mn is not None and val < mn: return False, f"out of range < {mn}"
        if mx is not None and val > mx: return False, f"out of range > {mx}"
        return True, ""
    if t == "float":
        # allow int for float inputs too
        if not isinstance(val, (int, float)):
            return False, "expected float"
        v = float(val)
        mn, mx = c.get("min"), c.get("max")
        if mn is not None and v < mn: return False, f"out of range < {mn}"
        if mx is not None and v > mx: return False, f"out of range > {mx}"
        return True, ""
    return True, ""  # unknown -> accept

def _format_actuator(item: Dict[str, Any]) -> str:
    desc = item.get("description", item.get("id", "appliance"))
    val_type = item.get("value_type")
    val = item.get("value")
    constraints = item.get("constraints", {})
    ok, why = _check_constraint(val, constraints)

    extra_invalid = f" [INVALID: {why}]" if not ok else ""

    # Special cases by type/description
    name_lower = desc.lower()
    def is_door_or_window() -> bool:
        return ("door" in name_lower) or ("window" in name_lower) or ("slider" in name_lower)

    if val_type == "boolean":
        if "lock" in name_lower or "servo" in item.get("id","").lower():
            state = "has locked" if val else "has unlocked"
            return f'{desc} {state}{extra_invalid}'
        # LED, pump on/off, etc.
        state = "has turned on" if val else "has turned off"
        return f'{desc} {state}{extra_invalid}'

    if val_type == "integer":
        # Treat as percentage
        pct = int(val)
        suffix = ""
        if is_door_or_window():
            if pct == 0:
                suffix = " (fully closed)"
            elif pct == 100:
                suffix = " (fully open)"
            else:
                suffix = " (half open)"
        return f'{desc} set to {pct}%{suffix}{extra_invalid}'

    if val_type == "float":
        # Rare for actuator, but handle anyway
        return f'{desc} set to {float(val):.1f}{extra_invalid}'

    # Fallback
    return f'{desc} value={val}{extra_invalid}'

def _format_sensor(item: Dict[str, Any]) -> str:
    desc = item.get("description", item.get("id", "sensor"))
    val_type = item.get("value_type")
    val = item.get("value")
    constraints = item.get("constraints", {})
    ok, why = _check_constraint(val, constraints)
    extra_invalid = f" [INVALID: {why}]" if not ok else ""

    name_lower = desc.lower()
    if val_type == "boolean":
        # PIR
        if "pir" in name_lower:
            state = "detected people inside (pir)" if val else "no motion detected (pir)"
            return f'{desc} {state}{extra_invalid}'
        # generic boolean sensor
        state = "true" if val else "false"
        return f'{desc} in "{room}" {state}{extra_invalid}'

    if val_type == "float":
        if "moisture" in name_lower or "mois" in item.get("id","").lower():
            return f'{desc} {float(val):.1f} %moist{extra_invalid}'
        # temperature
        return f'{desc} in {float(val):.1f} Celsius degree{extra_invalid}'

    # Fallback
    return f'{desc} in value={val}{extra_invalid}'

def format_all_statuses_from_dict(data: Dict[str, Any]) -> str:
    root = data.get("List_of house appliance (current values)", {})
    lines: List[str] = []
    for room, block in root.items():
        if not isinstance(block, dict): 
            continue
        # Skip espID in output (but keep room name)

        lines.append(f"{room}:")
        room = room.lower()
        for kind in ("actuator", "sensor"):
            for item in block.get(kind, []):
                if kind == "actuator":
                    lines.append(_format_actuator(item))
                else:
                    lines.append(_format_sensor(item))
        lines.append("")
    return "\n".join(lines)


###### GET ALL APPLIANCES STATUS ######
def get_all_appliances_status() -> str:
    path = _APPLIANCES_FILE
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return format_all_statuses_from_dict(data)

###### GET APPLIANCE STATUS ######
def get_appliance_value(esp_id: int, device_name: str) -> str:
    """
    Look up an appliance/sensor by esp_id and device_name (e.g., 'led1', 'fan1', 'door', 'pir')
    using data loaded from 'appliances_data.json', then return a single human-readable status line:
        Light in "Livingroom" has turned off
    """

    if not _APPLIANCES_FILE.exists():
        return f'Data file "{_APPLIANCES_FILE}" not found.'

    try:
        data = json.loads(_APPLIANCES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f'Failed to load "{_APPLIANCES_FILE}": {e}'

    def _find_room_by_esp(d: Dict[str, Any], esp: int) -> Tuple[str, Dict[str, Any]]:
        root = d.get("List_of house appliance (current values)", {})
        for room_name, block in root.items():
            if isinstance(block, dict) and block.get("espID") == esp:
                return room_name, block
        return "", {}

    def _check_constraint(val: Any, c: Dict[str, Any]) -> Tuple[bool, str]:
        t = (c or {}).get("type")
        if t == "boolean":
            return (isinstance(val, bool), "expected boolean" if not isinstance(val, bool) else "")
        if t == "integer":
            if not isinstance(val, int):
                return False, "expected integer"
            mn, mx = c.get("min"), c.get("max")
            if mn is not None and val < mn: return False, f"out of range < {mn}"
            if mx is not None and val > mx: return False, f"out of range > {mx}"
            return True, ""
        if t == "float":
            if not isinstance(val, (int, float)):
                return False, "expected float"
            v = float(val)
            mn, mx = c.get("min"), c.get("max")
            if mn is not None and v < mn: return False, f"out of range < {mn}"
            if mx is not None and v > mx: return False, f"out of range > {mx}"
            return True, ""
        return True, ""  # accept unknown

    def _fmt_actuator_line(room: str, item: Dict[str, Any]) -> str:
        desc = item.get("description", item.get("id", "appliance"))
        vtype = (item.get("value_type") or "").lower()
        val = item.get("value")
        ok, why = _check_constraint(val, item.get("constraints", {}))
        invalid = f" [INVALID: {why}]" if not ok else ""

        name_l = (desc or "").lower()
        # boolean (lights, servo/lock)
        if vtype == "boolean":
            if "lock" in name_l or item.get("id", "").lower().startswith("servo"):
                return f'{desc.title()} in "{room}" ' + ("has locked" if val else "has unlocked") + invalid
            return f'{desc.title()} in "{room}" ' + ("has turned on" if val else "has turned off") + invalid

        # integer (%) — fans, sliders, pumps, etc.
        if vtype == "integer":
            pct = int(val)
            suffix = ""
            if any(k in name_l for k in ("door", "window", "slider")):
                suffix = " (fully closed)" if pct == 0 else " (fully open)"
            return f'{desc.title()} in "{room}" set to {pct}%{suffix}{invalid}'

        # float (rare for actuator)
        if vtype == "float":
            return f'{desc.title()} in "{room}" set to {float(val):.1f}{invalid}'

        return f'{desc.title()} in "{room}" value={val}{invalid}'

    def _fmt_sensor_line(room: str, item: Dict[str, Any]) -> str:
        desc = item.get("description", item.get("id", "sensor"))
        vtype = (item.get("value_type") or "").lower()
        val = item.get("value")
        ok, why = _check_constraint(val, item.get("constraints", {}))
        invalid = f" [INVALID: {why}]" if not ok else ""

        name_l = (desc or "").lower()
        if vtype == "boolean":
            # PIR
            if "pir" in name_l or item.get("id", "").lower() == "pir":
                return f'{desc.title()} in "{room}" ' + ("detected people inside (pir)" if val else "no motion detected (pir)") + invalid
            return f'{desc.title()} in "{room}" ' + ("true" if val else "false") + invalid

        if vtype == "float":
            if "moisture" in name_l or item.get("id", "").lower() in ("mois", "moisture"):
                return f'{desc.title()} in "{room}" {float(val):.1f} %moist{invalid}'
            return f'{desc.title()} in "{room}" {float(val):.1f} Celsius degree{invalid}'

        return f'{desc.title()} in "{room}" value={val}{invalid}'

    def _normalize(s: str) -> str:
        return "".join(ch for ch in s.lower().strip() if ch.isalnum())

    def _split_base_num(s: str) -> Tuple[str, int]:
        base, num = "", ""
        for ch in s:
            if ch.isdigit():
                num += ch
            else:
                base += ch
        return base, (int(num) if num else -1)

    # ---- search in JSON ----
    room_name, room_block = _find_room_by_esp(data, esp_id)
    if not room_block:
        return f'Room with espID={esp_id} not found.'

    target = _normalize(device_name)
    base, num = _split_base_num(target)

    # collect candidates
    candidates: List[Tuple[str, Dict[str, Any], str]] = []
    for kind in ("actuator", "sensor"):
        for item in room_block.get(kind, []):
            line = _fmt_actuator_line(room_name, item) if kind == "actuator" else _fmt_sensor_line(room_name, item)
            candidates.append((kind, item, line))

    # exact id match
    for kind, item, line in candidates:
        if _normalize(item.get("id", "")) == target:
            return line

    # heuristic match (base + numeric suffix + synonyms)
    def _id_suffix(i: str) -> int:
        suf = "".join(ch for ch in i if ch.isdigit())
        return int(suf) if suf else -1

    ranked: List[Tuple[int, str]] = []
    for kind, item, line in candidates:
        idn = _normalize(item.get("id", ""))
        descl = _normalize(item.get("description", ""))
        score = 0

        if base and (base in idn or base in descl):
            score += 2
        if num != -1 and _id_suffix(item.get("id", "")) == num:
            score += 2
        # map fan->motor, door/window/slider->desc, lock->servo
        if base in ("fan",) and idn.startswith("motor"):
            score += 1
        if base in ("door", "window", "slider") and (("door" in descl) or ("window" in descl) or ("slider" in descl)):
            score += 1
        if base in ("lock", "servo") and (idn.startswith("servo") or "lock" in descl):
            score += 1

        if score > 0:
            ranked.append((score, line))

    if ranked:
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return ranked[0][1]

    return f'Device "{device_name}" not found in espID={esp_id}.'




###### SET APPLIANCE VALUE ######
def set_appliance_value(esp_id: int, device_name: str, value) -> str:
    if not _APPLIANCES_FILE.exists():
        return f'Data file "{_APPLIANCES_FILE}" not found.'
    try:
        data = json.loads(_APPLIANCES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f'Failed to load "{_APPLIANCES_FILE}": {e}'

    def _find_room_by_esp(d: Dict[str, Any], esp: int) -> Tuple[str, Dict[str, Any]]:
        root = d.get("List_of house appliance (current values)", {})
        for room_name, block in root.items():
            if isinstance(block, dict) and block.get("espID") == esp:
                return room_name, block
        return "", {}

    def _normalize(s: str) -> str:
        return "".join(ch for ch in (s or "").lower().strip() if ch.isalnum())

    def _split_base_num(s: str) -> Tuple[str, int]:
        base, num = "", ""
        for ch in s:
            if ch.isdigit():
                num += ch
            else:
                base += ch
        return base, (int(num) if num else -1)

    def _id_suffix(i: str) -> int:
        suf = "".join(ch for ch in i if ch.isdigit())
        return int(suf) if suf else -1

    room_name, room_block = _find_room_by_esp(data, esp_id)
    if not room_block:
        return f'Room with espID={esp_id} not found.'

    target = _normalize(device_name)
    base, num = _split_base_num(target)

    items: List[Tuple[str, Dict[str, Any]]] = []
    for kind in ("actuator", "sensor"):
        for item in room_block.get(kind, []):
            items.append((kind, item))

    chosen = None
    for kind, item in items:
        if _normalize(item.get("id", "")) == target:
            chosen = (kind, item)
            break
    if not chosen:
        ranked: List[Tuple[int, Tuple[str, Dict[str, Any]]]] = []
        for kind, item in items:
            idn = _normalize(item.get("id", ""))
            descl = _normalize(item.get("description", ""))
            score = 0
            if base and (base in idn or base in descl):
                score += 2
            if num != -1 and _id_suffix(item.get("id", "")) == num:
                score += 2
            if base in ("fan",) and idn.startswith("motor"):
                score += 1
            if base in ("door", "window", "slider") and (("door" in descl) or ("window" in descl) or ("slider" in descl)):
                score += 1
            if base in ("lock", "servo") and (idn.startswith("servo") or "lock" in descl):
                score += 1
            if score > 0:
                ranked.append((score, (kind, item)))
        if ranked:
            ranked.sort(key=lambda x: (-x[0], _normalize(x[1][1].get("id", ""))))
            chosen = ranked[0][1]

    if not chosen:
        return f'Device "{device_name}" not found in espID={esp_id}.'

    kind, item = chosen
    vtype = (item.get("value_type") or "").lower()
    constraints = item.get("constraints", {}) or {}

    try:
        if vtype == "boolean":
            if isinstance(value, str):
                lv = value.strip().lower()
                if lv in ("true", "1", "yes", "on"):
                    item["value"] = True
                elif lv in ("false", "0", "no", "off"):
                    item["value"] = False
                else:
                    return f'Invalid boolean value "{value}" for {device_name}'
            else:
                item["value"] = bool(value)
        elif vtype == "integer":
            iv = int(value)
            mn, mx = constraints.get("min"), constraints.get("max")
            if mn is not None and iv < mn:
                iv = mn
            if mx is not None and iv > mx:
                iv = mx
            item["value"] = iv
        elif vtype == "float":
            fv = float(value)
            mn, mx = constraints.get("min"), constraints.get("max")
            if mn is not None and fv < mn:
                fv = mn
            if mx is not None and fv > mx:
                fv = mx
            item["value"] = fv
        else:
            item["value"] = value
    except Exception as e:
        return f'Failed to set value for "{device_name}" in espID={esp_id}: {e}'

    try:
        _APPLIANCES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return f'Failed to save "{_APPLIANCES_FILE}": {e}'

    return get_appliance_value(esp_id, device_name)




###### RESET ALL APPLIANCE VALUE ######
def reset_all_appliances_value() -> str:
    if not _APPLIANCES_FILE.exists():
        return f'Data file "{_APPLIANCES_FILE}" not found.'
    try:
        data = json.loads(_APPLIANCES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f'Failed to load "{_APPLIANCES_FILE}": {e}'

    root = data.get("List_of house appliance (current values)", {})
    for _, block in root.items():
        for kind in ("actuator", "sensor"):
            for item in block.get(kind, []):
                vtype = (item.get("value_type") or "").lower()
                if vtype == "boolean":
                    item["value"] = False
                elif vtype == "integer":
                    item["value"] = 0
                elif vtype == "float":
                    if "tem" in item.get("id"):
                        item["value"] = 25.0
                    elif"mois" in item.get("id"):
                        item["value"] = 50.0
                    else:
                        item["value"] = 0.0

    try:
        _APPLIANCES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return f'Failed to save "{_APPLIANCES_FILE}": {e}'
    return "All appliances reset."

###### RESET APPLIANCE VALUE ######
def reset_appliance_value(esp_id: int, device_name: str) -> str:
    if not _APPLIANCES_FILE.exists():
        return f'Data file "{_APPLIANCES_FILE}" not found.'
    try:
        data = json.loads(_APPLIANCES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return f'Failed to load "{_APPLIANCES_FILE}": {e}'

    def _find_room_by_esp(d: Dict[str, Any], esp: int) -> Tuple[str, Dict[str, Any]]:
        root = d.get("List_of house appliance (current values)", {})
        for room_name, block in root.items():
            if isinstance(block, dict) and block.get("espID") == esp:
                return room_name, block
        return "", {}

    def _normalize(s: str) -> str:
        return "".join(ch for ch in (s or "").lower().strip() if ch.isalnum())

    room_name, room_block = _find_room_by_esp(data, esp_id)
    if not room_block:
        return f'Room with espID={esp_id} not found.'

    target = _normalize(device_name)
    items: List[Dict[str, Any]] = []
    for kind in ("actuator", "sensor"):
        for item in room_block.get(kind, []):
            items.append(item)

    chosen = None
    for item in items:
        if _normalize(item.get("id", "")) == target:
            chosen = item
            break
    if not chosen:
        return f'Device "{device_name}" not found in espID={esp_id}.'

    vtype = (chosen.get("value_type") or "").lower()
    if vtype == "boolean":
        chosen["value"] = False
    elif vtype == "integer":
        chosen["value"] = 0
    elif vtype == "float":
        if "tem" in (chosen.get("value_type") or "").lower():
            chosen["value"] = 25.0
        elif "mois" in (chosen.get("value_type") or "").lower():
            chosen["value"] = 50.0
        else:
            chosen["value"] = 0.0

    try:
        _APPLIANCES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return f'Failed to save "{_APPLIANCES_FILE}": {e}'
    return get_appliance_value(esp_id, device_name)




def execute_appliance(json_str: str) -> str:
    def to_str(v):
        if v is None: return ""
        if isinstance(v, float):
            s = f"{v:.6g}"
            return s
        return str(v)

    def is_uniform_obj_list(lst):
        if not lst or not all(isinstance(x, dict) for x in lst):
            return False, []
        key_sets = [tuple(sorted(d.keys())) for d in lst]
        first = key_sets[0]
        if not all(k == first for k in key_sets):
            return False, []
        return True, list(first)

    def table_from_obj_list(lst, cols):
        col_widths = {c: max(len(c), *(len(to_str(row.get(c, ""))) for row in lst)) for c in cols}
        header = " | ".join(c.ljust(col_widths[c]) for c in cols)
        sep = "-+-".join("-" * col_widths[c] for c in cols)
        lines = [header, sep]
        for row in lst:
            line = " | ".join(to_str(row.get(c, "")).ljust(col_widths[c]) for c in cols)
            lines.append(line)
        return "\n".join(lines)

    def kv_format(obj, indent=0, key=None):
        pad = "  " * indent
        lines = []
        if isinstance(obj, dict):
            if key is not None:
                lines.append(f"{pad}{key}:")
                pad += "  "
            for k in obj:
                lines.extend(kv_format(obj[k], indent + (1 if key is not None else 0), str(k)))
        elif isinstance(obj, list):
            if key is not None:
                lines.append(f"{pad}{key}:")
                pad += "  "
            for i, item in enumerate(obj):
                label = f"[{i}]"
                if isinstance(item, (dict, list)):
                    lines.extend(kv_format(item, indent + (1 if key is not None else 0), label))
                else:
                    lines.append(f"{pad}{label}: {to_str(item)}")
        else:
            if key is None:
                lines.append(f"{pad}{to_str(obj)}")
            else:
                lines.append(f"{pad}{key}: {to_str(obj)}")
        return lines

    data = json.loads(json_str)

    log_check = ""

    if isinstance(data, list):
        new_data = []
        for item in data:
            keep_item = Truekeep_item = True
            if not isinstance(item, dict):
                continue
            action = (item.get("action") or "").lower()
            if all(n not in action for n in ["set", "get"]):
                log_check += f'Action "{action}" is not recognized\n'
                continue
            esp = item.get("espID")
            dev = item.get("device_name")
            if action == "set" and esp is not None and isinstance(dev, str) and dev.strip():
                if all(n not in dev.lower() for n in ["led", "motor", "servo", "pump"]) and any(n in dev.lower() for n in ["tem", "mois", "pir"]):
                    log_check += f'Device "{dev}" is sensor and dont have "set" action\n'
                    keep_item = False
                    continue
                set_appliance_value(int(esp), dev, item.get("value"))
            new_data.append(item)

    if isinstance(new_data, list):
        uniform, cols = is_uniform_obj_list(new_data)
        out = table_from_obj_list(new_data, cols) if uniform else "\n".join(kv_format(new_data))
    elif isinstance(new_data, dict):
        out = "\n".join(kv_format(new_data))
    else:
        out = to_str(new_data)

    status_lines = []
    try:
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                esp = item.get("espID")
                dev = item.get("device_name")
                if esp is None or not isinstance(dev, str) or not dev.strip():
                    continue
                try:
                    status = get_appliance_value(int(esp), dev)
                except Exception as e:
                    status = f"[{idx}] Error while reading appliance ({esp}, {dev}): {e}"
                status_lines.append(f"- {status}")
    except Exception as e:
        status_lines.append(f"(Failed to append appliance statuses: {e})")

    if status_lines:
        out = f"{out}\n---\nCurrent appliance status:\n" + "\n".join(status_lines)

    return f"{log_check}{out}", f"\nCurrent appliance status:\n" + "\n".join(status_lines)



if __name__ == "__main__":
    # print(get_current_datetime_tool())

    string = "[{\"espID\": 2, \"device_type\": \"actuator\", \"device_name\": \"led1\", \"action\": \"set\", \"value\": true}, \
               {\"espID\": 3, \"device_type\": \"actuator\", \"device_name\": \"motor1\", \"action\": \"set\", \"value\": 50}, \
               {\"espID\": 3, \"device_type\": \"sensor\", \"device_name\": \"mois\", \"action\": \"set\", \"value\": 20}]"
    formated, log_to_save = execute_appliance(string)
    print(log_to_save)
    print(formated)
    print("-----")
    reset_all_appliances_value()
    print(get_all_appliances_status())
    # print(get_current_datetime())