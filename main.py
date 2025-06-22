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
    url = f"https://api.thingiverse.com/newest/things"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (ThingiverseBot)"
    }
    params = {
        "access_token": APP_TOKEN
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        print("📥 Raw response:", response.text)
        data = response.json()

        if "hits" in data and len(data["hits"]) > 0:
            item = data["hits"][0]
            name = item.get("name", "No Name")
            public_url = item.get("public_url", "")
            image = item.get("thumbnail", "")
            message = f"📦 {name}\n🔗 {public_url}\n🖼 {image}"
            send_telegram_message(message)
        else:
            send_telegram_message("⚠️ لا توجد تصميمات جديدة")
    except Exception as e:
        print("❌ Error fetching from Thingiverse:", e)
        send_telegram_message(f"❌ خطأ في جلب التصميمات: {e}")

def heartbeat():
    while True:
        fetch_latest_design()
        time.sleep(60)

if __name__ == "__main__":
    Thread(target=heartbeat).start()
    app.run(host="0.0.0.0", port=10000)
