

import os, time, json, traceback, requests
from datetime import datetime
from threading import Thread

import cloudscraper
from flask import Flask

#─────

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN must be set!"

#───── Flask ─────

app = Flask(name)
@app.route("/")
def index():
return "✅ Thingiverse-Bot is running."

#───── Telegram & Thingiverse ─────

scraper = cloudscraper.create_scraper(
browser={"browser": "firefox", "platform": "linux", "desktop": True}
)
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str):
kb = {
"inline_keyboard": [
[
{"text": "🔗 View on Thingiverse", "url": view_url},
{"text": "⬇️ Download STL",       "url": dl_url},
]
]
}
payload = {
"chat_id": CHAT_ID,
"photo":   photo_url,
"caption": caption,
"reply_markup": json.dumps(kb, ensure_ascii=False)
}
scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str):
scraper.post(f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt}, timeout=10)

API_ROOT = "https://api.thingiverse.com"
last_id  = None

def newest_thing():
url = f"{API_ROOT}/newest/things"
r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
r.raise_for_status()
data = r.json() if r.headers.get("content-type","").startswith("application/json") else None
if not data:
raise ValueError("HTML response (Cloudflare).")
return data[0] if isinstance(data, list) and data else None

def first_file_id(thing_id: int):
url = f"{API_ROOT}/things/{thing_id}/files"
r   = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
r.raise_for_status()
files = r.json()
return files[0]["id"] if isinstance(files, list) and files else None

def worker():
global last_id
while True:
try:
thing = newest_thing()
if thing and thing["id"] != last_id:
last_id = thing["id"]
title   = thing.get("name", "Thing")
pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{last_id}"
thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
file_id = first_file_id(last_id)
dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
caption = f"📦 {title}"
tg_photo(thumb, caption, pub_url, dl_url)
except Exception as e:
print("⚠️", traceback.format_exc(limit=1))
tg_text(f"❌ خطأ في جلب التصميمات:\n{e}")

now = datetime.now().strftime("%H:%M:%S")  
    tg_text(f"🤖 new update coming - {now}")  
    time.sleep(120)

#─────────

if name == "main":
Thread(target=worker, daemon=True).start()
Thread(target=keep_alive, daemon=True).start()
app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

