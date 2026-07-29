# 🌧️ Rain Watch

Rain Watch is a simple Python application that checks the weather forecast for the **next 15 hours** using the OpenWeatherMap API. If rain is expected, it automatically sends an SMS reminder via Twilio so you don't forget to carry an umbrella.

## Features

- Checks the weather forecast for the next 15 hours.
- Detects upcoming rain based on weather conditions.
- Sends an SMS alert using Twilio.
- Uses environment variables to securely store API keys and credentials.

## Technologies Used

- Python
- Requests
- Twilio API
- OpenWeatherMap API

## Prerequisites

Before running the project, you'll need:

- Python 3.x
- An OpenWeatherMap API key
- A Twilio account with:
  - Account SID
  - Auth Token
  - Twilio phone number

## Environment Variables

Create the following environment variables:

```text
ACCOUNT_ID=your_twilio_account_sid
AUTH_KEY=your_twilio_auth_token
APP_KEY=your_openweathermap_api_key
MY_LAT=your_latitude
MY_LON=your_longitude
FROM_NUMBER=your_twilio_phone_number
TO_NUMBER=your_phone_number
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/rain-watch.git
```

2. Navigate to the project directory:

```bash
cd rain-watch
```

3. Install the required dependencies:

```bash
pip install requests twilio
```

## Usage

Run the application:

```bash
python main.py
```

## 📸 Results

### SMS Notification

![SMS Alert](assets/screenshot_sms.jpeg)

## Project Structure

```
Rain-Watch/
│
├── main.py
├── assets
├── README.md
└── .env (optional)
```

## Future Improvements

- Support multiple locations.
- Send notifications via email or Telegram.
- Allow users to customize the forecast duration.
- Deploy as a scheduled cloud service.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

**Akash Anand**
