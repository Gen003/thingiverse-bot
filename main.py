import os
import time
import requests
from flask import Flask
from threading import Thread
from datetime import datetime

app = Flask(__name__)

def send_telegram_message(text):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"⚠️ Failed to send message. Code: {response.status_code}")
                print(response.text)
            else:
                print(f"✅ Message sent at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print("❌ Exception:", e)
    else:
        print("❌ BOT_TOKEN or CHAT_ID missing")

def heartbeat_loop():
    while True:
        now = datetime.now().strftime("%H:%M:%S")
        send_telegram_message(f"🤖 البوت حي - {now}")
        time.sleep(60)

@app.route('/')
def home():
    return "✅ Thingiverse Bot is running."

# ✅ نشغّل الخيط مباشرة هنا
def start_heartbeat():
    print("🧠 Starting heartbeat thread")
    t = Thread(target=heartbeat_loop)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    print("🚀 Launching bot service")
    start_heartbeat()
    app.run(host="0.0.0.0", port=10000)
