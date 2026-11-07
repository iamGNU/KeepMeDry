# 🌧️ KeepMeDry

KeepMeDry is a free, open-source Telegram bot that warns you when rain is on the way. Anyone can subscribe: open the bot, tap **Start** and share a location (or type a city name). Each morning, subscribers whose forecast shows rain in the next 15 hours get a message like:

> 🌧️ Rain expected in Pune, Maharashtra, India: light rain 08:00–10:00, thunderstorm at 14:00.
> Don't forget your umbrella ☔

It costs nothing to run: weather comes from [Open-Meteo](https://open-meteo.com/) (free, no API key), and the bot runs on GitHub Actions, so there's no server to host.

## Using the bot

1. Open [@KeepMeDryBot](https://t.me/KeepMeDryBot) in Telegram and tap **Start**.
2. Tap **📍 Share my location**, or type your city name (e.g. `Pune`).
3. That's it. You'll get a message around 07:00 your local time on days when rain is expected.

| Command   | What it does                          |
|-----------|---------------------------------------|
| `/now`    | Check the forecast right now          |
| `/status` | Show your location and alert time     |
| `/stop`   | Unsubscribe                           |

To change location, share a new one or type another city name.

Replies aren't instant: the bot checks for new messages every 15 minutes, and GitHub sometimes delays these runs further.

## How it works

Every 15 minutes, a GitHub Actions workflow runs `main.py`, which:

1. Fetches new Telegram messages and handles them (subscribe, `/stop`, ...).
2. For each subscriber whose local time has passed `ALERT_HOUR`, checks the forecast once for the day and sends an alert if rain is expected. Subscribers in the same area share one forecast request.
3. Saves the subscriber list, encrypted, to the repository's `data` branch.

Subscriber data (Telegram chat IDs and locations rounded to about 1 km) is encrypted with `DATA_KEY`, so it stays private even though the repository is public. The workflow logs only counts, never names or locations.

## Setting up your own bot

1. **Create the bot.** In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot` and follow the steps. Copy the token it gives you.
2. **Optional: add the command menu and a description.** Still in @BotFather:
   - `/setcommands`, choose your bot, and send:
     ```
     now - Check the forecast right now
     status - Show your subscription
     stop - Unsubscribe
     ```
   - `/setdescription`: e.g. "Get a morning alert when rain is forecast where you are. Replies can take a few minutes."
3. **Generate an encryption key:**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Keep it safe. If you lose it, the saved subscriber list can't be read.
4. **Add repository secrets** under **Settings → Secrets and variables → Actions → Secrets**:
   - `TELEGRAM_BOT_TOKEN`: the token from step 1
   - `DATA_KEY`: the key from step 3
5. **Optional: add repository variables** on the **Variables** tab of the same page:
   - `ALERT_HOUR`: local hour to send alerts (default `7`)
   - `FORECAST_HOURS`: how many hours ahead to check (default `15`)
6. **Run it.** Push to GitHub, then open the **Actions** tab, choose **KeepMeDry** and click **Run workflow**. After that it runs every 15 minutes on its own.

GitHub Actions is free for public repositories. GitHub may pause scheduled workflows in repositories with no activity for 60 days; if that happens, re-enable it from the **Actions** tab.

## Running locally

```bash
git clone https://github.com/iamGNU/KeepMeDry.git
cd KeepMeDry
pip install -r requirements-dev.txt
cp .env.example .env    # then fill in TELEGRAM_BOT_TOKEN and DATA_KEY
python main.py          # handles pending messages and due alerts, then exits
pytest                  # run the tests
```

Locally, subscribers are stored in `data/subscribers.enc`. This is separate from the copy GitHub Actions keeps on the `data` branch. Don't run the bot locally while the workflow is active with the same token: both would compete for the same messages.

## Project structure

```
KeepMeDry/
├── .github/workflows/main.yml   # Runs the bot every 15 min; runs tests on push
├── main.py                      # Entry point: one run of the bot
├── bot.py                       # Message handling and daily alerts
├── weather.py                   # Open-Meteo forecast and city lookup
├── telegram_api.py              # Small Telegram Bot API client
├── storage.py                   # Encrypted subscriber storage
├── tests/                       # Pytest tests
├── requirements.txt             # Runtime dependencies
└── requirements-dev.txt         # Test/dev dependencies
```

## Future improvements

- Instant replies by switching from polling to a webhook on a free host.
- Let each subscriber choose their own alert time.
- Multiple locations per subscriber.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

**Akash Anand**
