"""KeepMeDry Telegram bot logic: handle subscriber messages and send daily alerts."""

from datetime import datetime
from zoneinfo import ZoneInfo

import weather
from telegram_api import BotBlocked, TelegramAPI, TelegramError

# Alerts are sent if the first run after ALERT_HOUR happens within this many hours.
# Later than that (e.g. after a long GitHub outage) the day's alert is skipped.
ALERT_WINDOW_HOURS = 3

LOCATION_KEYBOARD = {
    "keyboard": [[{"text": "📍 Share my location", "request_location": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
REMOVE_KEYBOARD = {"remove_keyboard": True}

HELP_TEXT = (
    "🌧️ KeepMeDry sends you a message each morning when rain is expected where you are.\n\n"
    "To subscribe, tap “📍 Share my location” or type the name of your city.\n\n"
    "Commands:\n"
    "/now – check the forecast right now\n"
    "/status – show your subscription\n"
    "/stop – unsubscribe\n\n"
    "Replies can take a few minutes."
)


class RainBot:
    def __init__(self, api: TelegramAPI, data: dict, alert_hour: int = 7, forecast_hours: int = 15):
        self.api = api
        self.data = data
        self.alert_hour = alert_hour
        self.forecast_hours = forecast_hours
        self.subscribers: dict = data["subscribers"]
        self._rain_cache: dict = {}

    # ---------- incoming messages ----------

    def process_updates(self) -> int:
        """Handle all pending messages. Returns how many were handled."""
        handled = 0
        while True:
            updates = self.api.get_updates(self.data["offset"])
            if not updates:
                return handled
            for update in updates:
                # Advance first, so one bad message can never block the queue.
                self.data["offset"] = update["update_id"] + 1
                message = update.get("message")
                if not message:
                    continue
                chat_id = str(message["chat"]["id"])
                try:
                    self.handle_message(chat_id, message)
                except BotBlocked:
                    self.subscribers.pop(chat_id, None)
                except Exception as exc:  # keep going for everyone else
                    # Log only the error type: messages can contain locations, and the log is public.
                    print(f"Failed to handle a message: {type(exc).__name__}")
                    try:
                        self.api.send_message(chat_id, "Sorry, something went wrong. Please try again in a few minutes.")
                    except TelegramError:
                        pass
                handled += 1

    def handle_message(self, chat_id: str, message: dict) -> None:
        if "location" in message:
            loc = message["location"]
            self.subscribe(chat_id, loc["latitude"], loc["longitude"], place=None)
            return

        text = (message.get("text") or "").strip()
        command = text.split()[0].split("@")[0].lower() if text.startswith("/") else None

        if command in ("/start", "/help"):
            self.api.send_message(chat_id, HELP_TEXT, LOCATION_KEYBOARD)
        elif command == "/stop":
            if self.subscribers.pop(chat_id, None):
                self.api.send_message(chat_id, "You've been unsubscribed. Send /start any time to subscribe again.")
            else:
                self.api.send_message(chat_id, "You aren't subscribed. Send /start to subscribe.")
        elif command == "/status":
            self.send_status(chat_id)
        elif command == "/now":
            self.send_forecast_now(chat_id)
        elif command:
            self.api.send_message(chat_id, HELP_TEXT, LOCATION_KEYBOARD)
        elif text:
            place = weather.geocode(text)
            if place is None:
                self.api.send_message(
                    chat_id,
                    f"I couldn't find “{text}”. Try just the city name, or share your location.",
                    LOCATION_KEYBOARD,
                )
            else:
                self.subscribe(chat_id, place.lat, place.lon, place=place.name)

    def subscribe(self, chat_id: str, lat: float, lon: float, place: str | None) -> None:
        # Round to ~1 km: enough for a forecast, keeps less precise location data,
        # and lets nearby subscribers share one forecast request.
        lat, lon = round(lat, 2), round(lon, 2)
        tz = weather.fetch_timezone(lat, lon)
        local_now = datetime.now(ZoneInfo(tz))
        self.subscribers[chat_id] = {
            "lat": lat,
            "lon": lon,
            "place": place or f"{lat:.2f}, {lon:.2f}",
            "timezone": tz,
            # Don't send today's alert late in the day; start tomorrow morning.
            "last_checked": local_now.date().isoformat() if local_now.hour >= self.alert_hour else None,
        }
        self.api.send_message(
            chat_id,
            f"✅ Subscribed for {self.subscribers[chat_id]['place']}.\n\n"
            f"I'll message you around {self.alert_hour:02d}:00 ({tz}) on days when rain is expected "
            f"in the next {self.forecast_hours} hours. Send /now to check right away, or /stop to unsubscribe.",
            REMOVE_KEYBOARD,
        )

    def send_status(self, chat_id: str) -> None:
        sub = self.subscribers.get(chat_id)
        if not sub:
            self.api.send_message(chat_id, "You aren't subscribed. Send /start to subscribe.")
            return
        self.api.send_message(
            chat_id,
            f"📍 {sub['place']}\n⏰ Daily check around {self.alert_hour:02d}:00 ({sub['timezone']})\n\n"
            "To change location, share a new one or type a city name.",
        )

    def send_forecast_now(self, chat_id: str) -> None:
        sub = self.subscribers.get(chat_id)
        if not sub:
            self.api.send_message(chat_id, "Share your location or type a city name first.", LOCATION_KEYBOARD)
            return
        rain = self.rain_for(sub)
        if rain:
            self.api.send_message(chat_id, self.alert_text(sub, rain))
        else:
            self.api.send_message(chat_id, f"☀️ No rain expected in {sub['place']} in the next {self.forecast_hours} hours.")

    # ---------- daily alerts ----------

    def send_due_alerts(self, now: datetime) -> int:
        """Send today's alert to every subscriber whose local alert time has arrived. Returns alerts sent."""
        sent = 0
        for chat_id, sub in list(self.subscribers.items()):
            local = now.astimezone(ZoneInfo(sub["timezone"]))
            today = local.date().isoformat()
            if sub.get("last_checked") == today or local.hour < self.alert_hour:
                continue
            if local.hour >= self.alert_hour + ALERT_WINDOW_HOURS:
                sub["last_checked"] = today  # too late today; skip
                continue
            try:
                rain = self.rain_for(sub)
            except Exception as exc:  # forecast unavailable: retry on the next run
                print(f"Forecast failed: {type(exc).__name__}")
                continue
            sub["last_checked"] = today
            if not rain:
                continue
            try:
                self.api.send_message(chat_id, self.alert_text(sub, rain))
                sent += 1
            except BotBlocked:
                self.subscribers.pop(chat_id, None)
            except TelegramError as exc:
                print(f"Send failed: {exc}")
        return sent

    def rain_for(self, sub: dict) -> list[weather.RainHour]:
        key = (sub["lat"], sub["lon"])
        if key not in self._rain_cache:
            forecast = weather.fetch_forecast(sub["lat"], sub["lon"], self.forecast_hours)
            self._rain_cache[key] = weather.find_rain(forecast)
        return self._rain_cache[key]

    @staticmethod
    def alert_text(sub: dict, rain: list[weather.RainHour]) -> str:
        return (
            f"🌧️ Rain expected in {sub['place']}: {weather.summarize(rain)}.\n"
            "Don't forget your umbrella ☔"
        )
