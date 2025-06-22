import os
import time
import requests
from flask import Flask
from threading import Thread
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Thingiverse Bot is running."

def send_telegram_message(text):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print("❌ Error sending message:", e)

def heartbeat():
    while True:
        now = datetime.now().strftime("%H:%M:%S")
        send_telegram_message(f"🤖 البوت حي - {now}")
        time.sleep(60)  # كل 60 ثانية

if __name__ == "__main__":
    Thread(target=heartbeat).start()
    app.run(host="0.0.0.0", port=10000)