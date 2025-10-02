from datetime import datetime
import pandas as pd
import requests
import json

LOCATION_COORDS = {
    "current":(10.7769, 106.7009), # hochiminh city
    "ha noi": (21.0285, 105.8542),
    "ho chi minh city": (10.7769, 106.7009),
    "da nang": (16.0471, 108.2068),
    "hai phong": (20.8449, 106.6881),
    "hue": (16.4637, 107.5909),
}

def get_current_datetime():
    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = f"Current date: {datetime.now().strftime('%Y-%m-%d')} - Current time: {datetime.now().strftime('%H:%M:%S')}"

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

def get_hourly_forecast(place: str, date: str) -> str:
    if place.lower() not in LOCATION_COORDS or place.lower() == "current":
        latitude, longitude, city, country = get_current_location(True)
        noti = ""
        if place.lower() not in LOCATION_COORDS:
            noti = f"Place '{place}' not found in LOCATION_COORDS mapping, return current location.\nCurrent location: {city}, {country}:\n"
    else:
        latitude, longitude = LOCATION_COORDS[place.lower()]
        noti = ""

    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&hourly=temperature_2m,relative_humidity_2m,windspeed_10m,weathercode,cloudcover"
        f"&forecast_days=1&timezone=auto"
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

    if isinstance(data, list):
        uniform, cols = is_uniform_obj_list(data)
        out = table_from_obj_list(data, cols) if uniform else "\n".join(kv_format(data))
    elif isinstance(data, dict):
        out = "\n".join(kv_format(data))
    else:
        out = to_str(data)

    return out



if __name__ == "__main__":
    # print(get_current_datetime_tool())

    string = "[{\"espID\": 2, \"device_type\": \"actuator\", \"device_name\": \"led1\", \"action\": \"set\", \"value\": true}, {\"espID\": 3, \"device_type\": \"actuator\", \"device_name\": \"motor1\", \"action\": \"set\", \"value\": 50}]"
    print(execute_appliance(string))