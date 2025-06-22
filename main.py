import os
import time
import requests
from flask import Flask
from threading import Thread
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

@app.route('/')
def home():
    return "✅ Thingiverse Bot is running."

def send_telegram_message(text):
    if BOT_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print("❌ Error sending message:", e)

def fetch_latest_design():
    url = f"https://api.thingiverse.com/newest/things?access_token={APP_TOKEN}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; ThingiverseBot/1.0)"
    }
    try:
        response = requests.get(url, headers=headers)
        print("📥 Raw response:", response.text)  # <-- هام جدًا للطباعة
        data = response.json()
        for item in data.get("hits", []):
            name = item["name"]
            url = item["public_url"]
            image = item["thumbnail"]
            message = f"📦 {name}\n🔗 {url}\n🖼 {image}"
            send_telegram_message(message)
            break  # أرسل فقط أول تصميم
    except Exception as e:
        print("❌ Error fetching from Thingiverse:", e)

def heartbeat():
    while True:
        fetch_latest_design()
        time.sleep(60)

if __name__ == "__main__":
    Thread(target=heartbeat).start()
    app.run(host="0.0.0.0", port=10000)