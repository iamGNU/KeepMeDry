import os
import requests
from twilio.rest import Client

account_sid = os.getenv("ACCOUNT_ID")
auth_token = os.getenv("AUTH_KEY")

parameters = {
    "lat" : os.getenv("MY_LAT"),
    "lon": os.getenv("MY_LON"),
    "appid" : os.getenv("APP_KEY"),
    "cnt" : 5,
}

response = requests.get(url="https://api.openweathermap.org/data/2.5/forecast",params=parameters)
response.raise_for_status()
weather_data = response.json()
will_rain = False
for hour_data in weather_data["list"]:
    weather_id = hour_data["weather"][0]["id"]
    if weather_id<700 :
        will_rain = True
if will_rain:
    print("It is raining")
    client = Client(account_sid,auth_token)
    message = client.messages.create(
        body="Don't forget to take your umbrella☔",
        from_=os.getenv("FROM_NUMBER"),
        to=os.getenv("TO_NUMBER"),
    )
