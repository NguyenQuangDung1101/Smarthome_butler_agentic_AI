from datetime import datetime
import pandas as pd
import requests

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


if __name__ == "__main__":
    # print(get_current_datetime_tool())

    print(get_current_location())