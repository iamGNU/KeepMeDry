from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

import weather
from bot import RainBot
from storage import empty_data, load_data, save_data
from telegram_api import BotBlocked


# ---------- weather ----------

def forecast(codes, start_hour=6):
    return {
        "timezone": "Asia/Kolkata",
        "hourly": {
            "time": [f"2026-11-07T{start_hour + i:02d}:00" for i in range(len(codes))],
            "weather_code": codes,
        },
    }


def test_find_rain_only_returns_precipitation_hours():
    rain = weather.find_rain(forecast([0, 61, 3, 95, 45]))
    assert [(h.time, h.description) for h in rain] == [
        ("07:00", "light rain"),
        ("09:00", "thunderstorm"),
    ]


def test_find_rain_dry_forecast():
    assert weather.find_rain(forecast([0, 1, 2, 3, 45])) == []


def test_summarize_merges_consecutive_hours():
    rain = weather.find_rain(forecast([61, 61, 61, 0, 95, 61]))
    assert weather.summarize(rain) == (
        "light rain 06:00–08:00, thunderstorm at 10:00, light rain at 11:00"
    )


# ---------- storage ----------

def test_storage_round_trip_is_encrypted(tmp_path: Path):
    key = Fernet.generate_key().decode()
    path = tmp_path / "data" / "subscribers.enc"
    data = {"offset": 5, "subscribers": {"42": {"place": "Pune"}}}
    save_data(path, key, data)
    assert b"Pune" not in path.read_bytes()
    assert load_data(path, key) == data


def test_storage_missing_file_is_empty(tmp_path: Path):
    assert load_data(tmp_path / "nope.enc", Fernet.generate_key().decode()) == empty_data()


# ---------- bot ----------

class FakeAPI:
    def __init__(self, updates=None, blocked=()):
        self.batches = [updates or []]
        self.sent = []  # (chat_id, text)
        self.blocked = set(blocked)

    def get_updates(self, offset):
        return self.batches.pop(0) if self.batches else []

    def send_message(self, chat_id, text, reply_markup=None):
        if str(chat_id) in self.blocked:
            raise BotBlocked("blocked", 403)
        self.sent.append((str(chat_id), text))


def message(update_id, chat_id, **fields):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, **fields}}


@pytest.fixture
def fake_weather(monkeypatch):
    calls = []

    def fetch_forecast(lat, lon, hours):
        calls.append((lat, lon))
        return forecast([0, 61, 61])

    monkeypatch.setattr(weather, "fetch_forecast", fetch_forecast)
    monkeypatch.setattr(weather, "fetch_timezone", lambda lat, lon: "Asia/Kolkata")
    monkeypatch.setattr(
        weather, "geocode",
        lambda name: weather.Place("Pune, Maharashtra, India", 18.52, 73.86) if name == "Pune" else None,
    )
    return calls


def subscriber(**overrides):
    return {"lat": 18.52, "lon": 73.86, "place": "Pune", "timezone": "Asia/Kolkata",
            "last_checked": None, **overrides}


def test_start_sends_help(fake_weather):
    api = FakeAPI([message(1, 100, text="/start")])
    data = empty_data()
    RainBot(api, data).process_updates()
    assert api.sent[0][0] == "100"
    assert "Share my location" in api.sent[0][1]
    assert data["offset"] == 2


def test_location_subscribes_and_rounds(fake_weather):
    api = FakeAPI([message(1, 100, location={"latitude": 18.52049, "longitude": 73.85674})])
    data = empty_data()
    RainBot(api, data).process_updates()
    sub = data["subscribers"]["100"]
    assert (sub["lat"], sub["lon"], sub["timezone"]) == (18.52, 73.86, "Asia/Kolkata")
    assert "Subscribed" in api.sent[0][1]


def test_city_name_subscribes(fake_weather):
    api = FakeAPI([message(1, 100, text="Pune")])
    data = empty_data()
    RainBot(api, data).process_updates()
    assert data["subscribers"]["100"]["place"] == "Pune, Maharashtra, India"


def test_unknown_city_is_reported(fake_weather):
    api = FakeAPI([message(1, 100, text="Atlantis")])
    data = empty_data()
    RainBot(api, data).process_updates()
    assert data["subscribers"] == {}
    assert "couldn't find" in api.sent[0][1]


def test_stop_unsubscribes(fake_weather):
    api = FakeAPI([message(1, 100, text="/stop")])
    data = {"offset": 0, "subscribers": {"100": subscriber()}}
    RainBot(api, data).process_updates()
    assert data["subscribers"] == {}


def test_error_in_one_message_does_not_block_others(fake_weather, monkeypatch):
    def broken(name):
        raise RuntimeError("geocoder down")

    monkeypatch.setattr(weather, "geocode", broken)
    api = FakeAPI([message(1, 100, text="Pune"), message(2, 200, text="/start")])
    data = empty_data()
    RainBot(api, data).process_updates()
    assert data["offset"] == 3
    assert "went wrong" in api.sent[0][1]
    assert api.sent[1][0] == "200"


# 02:00 UTC = 07:30 in India
MORNING_IST = datetime(2026, 11, 7, 2, 0, tzinfo=timezone.utc)


def test_alert_sent_once_per_day(fake_weather):
    api = FakeAPI()
    data = {"offset": 0, "subscribers": {"100": subscriber()}}
    bot = RainBot(api, data)
    assert bot.send_due_alerts(MORNING_IST) == 1
    assert "light rain 07:00–08:00" in api.sent[0][1]
    assert data["subscribers"]["100"]["last_checked"] == "2026-11-07"
    assert bot.send_due_alerts(MORNING_IST) == 0


def test_no_alert_before_alert_hour(fake_weather):
    api = FakeAPI()
    data = {"offset": 0, "subscribers": {"100": subscriber()}}
    early = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)  # 05:30 IST
    assert RainBot(api, data).send_due_alerts(early) == 0
    assert data["subscribers"]["100"]["last_checked"] is None


def test_late_run_skips_the_day(fake_weather):
    api = FakeAPI()
    data = {"offset": 0, "subscribers": {"100": subscriber()}}
    late = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)  # 15:30 IST
    assert RainBot(api, data).send_due_alerts(late) == 0
    assert data["subscribers"]["100"]["last_checked"] == "2026-11-07"


def test_same_location_fetched_once(fake_weather):
    api = FakeAPI()
    data = {"offset": 0, "subscribers": {"100": subscriber(), "200": subscriber()}}
    assert RainBot(api, data).send_due_alerts(MORNING_IST) == 2
    assert len(fake_weather) == 1


def test_blocked_user_is_removed(fake_weather):
    api = FakeAPI(blocked={"100"})
    data = {"offset": 0, "subscribers": {"100": subscriber(), "200": subscriber()}}
    assert RainBot(api, data).send_due_alerts(MORNING_IST) == 1
    assert list(data["subscribers"]) == ["200"]


def test_no_message_when_dry(fake_weather, monkeypatch):
    monkeypatch.setattr(weather, "fetch_forecast", lambda lat, lon, hours: forecast([0, 1, 2]))
    api = FakeAPI()
    data = {"offset": 0, "subscribers": {"100": subscriber()}}
    assert RainBot(api, data).send_due_alerts(MORNING_IST) == 0
    assert api.sent == []
    assert data["subscribers"]["100"]["last_checked"] == "2026-11-07"
