import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

def send_telegram_message(text, image_url=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto" if image_url else f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "caption": text if image_url else None,
        "text": text if not image_url else None,
        "photo": image_url if image_url else None
    }
    requests.post(url, data=payload)

def fetch_and_send_latest():
    sent_ids = set()
    while True:
        try:
            res = requests.get(f"https://api.thingiverse.com/newest/things?access_token={APP_TOKEN}")
            things = res.json().get("hits", [])
            for thing in things:
                if thing["id"] not in sent_ids:
                    title = thing["name"]
                    url = thing["public_url"]
                    image = thing["thumbnail"]
                    message = f"🆕 *{title}*\n🔗 {url}"
                    send_telegram_message(message, image)
                    sent_ids.add(thing["id"])
            time.sleep(60)
        except Exception as e:
            print("❌ Error:", e)
            time.sleep(60)

@app.route('/')
def home():
    return "✅ Thingiverse Auto Bot Running"

if __name__ == "__main__":
    Thread(target=fetch_and_send_latest).start()
    app.run(host="0.0.0.0", port=10000)
