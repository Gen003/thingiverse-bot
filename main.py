import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

# للتأكد أن البوت يعمل على Render
@app.route('/')
def home():
    return "Thingiverse Bot is running!"

# إرسال رسالة تيليجرام
def send_telegram_message(text):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, data=payload)

# المهمة الرئيسية
def run_bot():
    while True:
        try:
            # أرسل فكرة جديدة كل 5 دقائق (عدّل كما تشاء)
            send_telegram_message("🛠️ فكرة جديدة: https://www.thingiverse.com/explore/newest")
            time.sleep(300)
        except Exception as e:
            print("خطأ:", e)
            time.sleep(60)

# تشغيل المهمة في الخلفية
def run_thread():
    thread = Thread(target=run_bot)
    thread.daemon = True
    thread.start()

# بدأ كل شيء
if __name__ == "__main__":
    run_thread()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
