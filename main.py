"""KeepMeDry: a Telegram bot that warns subscribers when rain is forecast.

Each run handles new messages (subscribe, /stop, ...) and sends the daily alerts
that are due, then exits. GitHub Actions runs it every 15 minutes.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bot import RainBot
from storage import load_data, save_data
from telegram_api import TelegramAPI

try:
    # Optional: load a local .env file when python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

REQUIRED_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "DATA_KEY")


def main() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        sys.exit(f"Missing required environment variables: {', '.join(missing)}")

    key = os.environ["DATA_KEY"]
    data_file = Path(os.getenv("DATA_FILE", "data/subscribers.enc"))
    data = load_data(data_file, key)
    original = json.dumps(data, sort_keys=True)
    bot = RainBot(
        TelegramAPI(os.environ["TELEGRAM_BOT_TOKEN"]),
        data,
        alert_hour=int(os.getenv("ALERT_HOUR", "7")),
        forecast_hours=int(os.getenv("FORECAST_HOURS", "15")),
    )
    try:
        handled = bot.process_updates()
        sent = bot.send_due_alerts(datetime.now(timezone.utc))
    finally:
        # Always save, so handled messages aren't processed twice. Only write when
        # something changed: encryption output differs every time, so rewriting an
        # unchanged file would create a commit on every run.
        if json.dumps(data, sort_keys=True) != original:
            save_data(data_file, key, data)
    # Only counts are logged: the Actions log of a public repo is public.
    print(f"Handled {handled} messages, sent {sent} alerts, {len(data['subscribers'])} subscribers.")


if __name__ == "__main__":
    main()
