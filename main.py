import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

def send_telegram_message(text, image_url=None):
    if image_url:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        data = {
            "chat_id": CHAT_ID,
            "caption": text,
            "photo": image_url
        }
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": text
        }
    try:
        response = requests.post(url, data=data)
        print("✅ Telegram Response:", response.status_code, response.text)
    except Exception as e:
        print("❌ Error sending to Telegram:", e)

def fetch_latest_design():
    url = f"https://api.thingiverse.com/newest/things?access_token={APP_TOKEN}"
    try:
        response = requests.get(url)
        data = response.json()
        if "hits" in data and len(data["hits"]) > 0:
            first = data["hits"][0]
            name = first.get("name")
            public_url = first.get("public_url")
            thumbnail = first.get("thumbnail")
            msg = f"🆕 {name}\n🔗 {public_url}"
            send_telegram_message(msg, image_url=thumbnail)
        else:
            send_telegram_message("⚠️ لا توجد تصميمات جديدة.")
    except Exception as e:
        print("❌ Error fetching from Thingiverse:", e)

# run once for test
fetch_latest_design()