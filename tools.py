from datetime import datetime
import pandas as pd
import requests
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, Optional
from bs4 import BeautifulSoup
import os
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

def search_and_read_web_link(
    query: str,
    num_results: int = 3,
    read: bool = True,
    api_key: Optional[str] = "d74c53982d4259c26022ca3e2a0c66d78e43e424057fb9dfa165cb93652b5164",
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






if __name__ == "__main__":
    # print(get_current_datetime())
    # print(get_current_location())
    print(get_hourly_forecast(False, None, 108.2068, "2025-12-20"))

    # res = serp_search_and_read("today news in viet nam", num_results=3, read=True)
    # print(res)