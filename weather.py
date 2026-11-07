"""Forecast and place lookup using Open-Meteo (free, no API key needed)."""

from dataclasses import dataclass

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather codes that mean some kind of precipitation.
PRECIPITATION_CODES = {
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "heavy freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "violent showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


@dataclass(frozen=True)
class RainHour:
    index: int  # position in the forecast, used to merge consecutive hours
    time: str  # local time, "HH:MM"
    description: str


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float


def fetch_forecast(lat: float, lon: float, hours: int) -> dict:
    """Hourly forecast for the next `hours` hours, with times in the place's local time zone."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "weather_code",
        "forecast_hours": hours,
        "timezone": "auto",
    }
    response = requests.get(FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_timezone(lat: float, lon: float) -> str:
    """IANA time zone name for a location, e.g. 'Asia/Kolkata'."""
    return fetch_forecast(lat, lon, 1)["timezone"]


def find_rain(forecast: dict) -> list[RainHour]:
    hourly = forecast["hourly"]
    return [
        RainHour(index=i, time=time[11:16], description=PRECIPITATION_CODES[code])
        for i, (time, code) in enumerate(zip(hourly["time"], hourly["weather_code"]))
        if code in PRECIPITATION_CODES
    ]


def summarize(rain: list[RainHour]) -> str:
    """Merge consecutive hours with the same weather, e.g. 'light rain 08:00–10:00, thunderstorm at 14:00'."""
    periods: list[list] = []  # [description, start_time, end_time, last_index]
    for hour in rain:
        last = periods[-1] if periods else None
        if last and last[0] == hour.description and last[3] == hour.index - 1:
            last[2], last[3] = hour.time, hour.index
        else:
            periods.append([hour.description, hour.time, hour.time, hour.index])
    return ", ".join(
        f"{desc} at {start}" if start == end else f"{desc} {start}–{end}"
        for desc, start, end, _ in periods
    )


def geocode(name: str) -> Place | None:
    """Look up a place by name, e.g. 'Pune' or 'Bandra, Mumbai'. Returns None if not found."""
    # The geocoder matches a single place name, so search on the first part only.
    query = name.split(",")[0].strip()
    if not query:
        return None
    response = requests.get(
        GEOCODE_URL, params={"name": query, "count": 1, "format": "json"}, timeout=15
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None
    top = results[0]
    label = ", ".join(part for part in (top.get("name"), top.get("admin1"), top.get("country")) if part)
    return Place(name=label, lat=top["latitude"], lon=top["longitude"])
