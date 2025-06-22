import os import time import cloudscraper  # للتغلب على حماية Cloudflare from flask import Flask from threading import Thread from datetime import datetime

app = Flask(name)

BOT_TOKEN = os.getenv("BOT_TOKEN") CHAT_ID = os.getenv("CHAT_ID") APP_TOKEN = os.getenv("APP_TOKEN")

نص ثابت للتأكد أن البوت حي

ALIVE_TEXT = "🤖 البوت حي"

Scraper خاص يتجاوز Cloudflare تلقائياً

scraper = cloudscraper.create_scraper(browser={ 'browser': 'firefox', 'platform': 'linux', 'desktop': True })

def send_telegram_message(text: str): """إرسال رسالة نصية إلى تيليجرام""" if not (BOT_TOKEN and CHAT_ID): print("⚠️ BOT_TOKEN أو CHAT_ID غير معرفين!") return url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" payload = {"chat_id": CHAT_ID, "text": text} try: scraper.post(url, data=payload, timeout=10) except Exception as e: print("❌ Error sending message:", e)

def fetch_latest_design(): """جلب أحدث تصميم منشور على Thingiverse""" api_url = "https://api.thingiverse.com/newest/things" params = {"access_token": APP_TOKEN}

try:
    r = scraper.get(api_url, params=params, timeout=15)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code}")

    data = r.json()  # قد يرمي استثناء إذا عاد نص HTML

    # Thingiverse يُرجع قائمة باسم "hits" أو مباشرة قائمة أشياء
    things = data.get("hits") or data
    if not things:
        print("⚠️ لا توجد عناصر في الرد.")
        return

    thing = things[0]
    title = thing.get("name", "No title")
    public_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing.get('id') }"
    thumb = thing.get("thumbnail") or thing.get("preview_image")

    msg = f"📦 {title}\n🔗 {public_url}"
    if thumb:
        # نرسل الصورة أولاً ثم العنوان كرابط (نستخدم sendPhoto)
        photo_url = thumb
        photo_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": CHAT_ID, "photo": photo_url, "caption": msg}
        scraper.post(photo_api, data=payload, timeout=10)
    else:
        send_telegram_message(msg)

except Exception as e:
    print("❌ Error fetching from Thingiverse:", e)
    send_telegram_message(f"❌ خطأ في جلب التصميمات: {e}")

def worker(): """حَلْقة لا نهائية: كل دقيقة يحاول جلب أحدث تصميم ويرسل Alive-ping.""" while True: fetch_latest_design() # Ping حيّ للتأكد أن البوت يعمل now = datetime.now().strftime("%H:%M:%S") send_telegram_message(f"{ALIVE_TEXT} - {now}") time.sleep(60)

@app.route("/") def index(): return "✅ Thingiverse Bot is running."

if name == "main": # بدء الخيط الخلفي Thread(target=worker, daemon=True).start() # تشغيل Flask app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

