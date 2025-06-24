# -*- coding: utf-8 -*-
"""
Ultimate STL Feeder → Telegram  ❚  د. إيرك 2025
يرسل أحدث/رائج/أكثر تحميلًا من Thingiverse, Printables, Cults3D
"""

import os, time, json, traceback, requests
from datetime import datetime
from threading import Thread
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN") # Thingiverse

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN must be set!"
SELF_URL = "https://thingiverse-bot.onrender.com"  # عدله حسب رابطك

app = Flask(__name__)
@app.route("/")
def index():
    return "✅ STL-Bot is running."

def keep_alive():
    while True:
        try: requests.get(SELF_URL)
        except: pass
        time.sleep(240)

TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_photo(photo_url, caption, kb):
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "reply_markup": json.dumps(kb, ensure_ascii=False)
    }
    requests.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=20)

def tg_text(txt):
    requests.post(f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt}, timeout=10)

#### 1. Thingiverse API ####
def thingiverse_fetch(endpoint="newest/things"):
    url = f"https://api.thingiverse.com/{endpoint}"
    r = requests.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    return r.json()

def thingiverse_latest():
    data = thingiverse_fetch("newest/things")
    for thing in data[:3]:  # أرسل آخر 3 لتقليل التكرار
        pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
        thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
        title   = thing.get("name", "Thing")
        file_id = first_thingiverse_file(thing["id"])
        dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
        kb = {"inline_keyboard": [[
            {"text": "Thingiverse ⬇️", "url": dl_url},
            {"text": "عرض التصميم", "url": pub_url}
        ]]}
        tg_photo(thumb, f"🌍 [Thingiverse]\n{title}", kb)

def thingiverse_popular():
    data = thingiverse_fetch("popular/things")
    for thing in data[:2]:
        pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
        thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
        title   = thing.get("name", "Thing")
        file_id = first_thingiverse_file(thing["id"])
        dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
        kb = {"inline_keyboard": [[
            {"text": "Thingiverse ⬇️", "url": dl_url},
            {"text": "رائج 🔥", "url": pub_url}
        ]]}
        tg_photo(thumb, f"🔥 [Thingiverse] رائج:\n{title}", kb)

def first_thingiverse_file(thing_id: int):
    url = f"https://api.thingiverse.com/things/{thing_id}/files"
    r   = requests.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    files = r.json()
    return files[0]["id"] if isinstance(files, list) and files else None

#### 2. Printables.com ####
def printables_latest():
    # Scraping because no official API
    try:
        resp = requests.get("https://www.printables.com/model", timeout=20)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select('a[data-cy="model-card-link"]')[:2]
        for a in cards:
            url  = "https://www.printables.com" + a['href']
            title = a.find("div", class_="card__title").text.strip()
            img   = a.find("img")['src']
            kb = {"inline_keyboard": [[
                {"text": "عرض على Printables", "url": url}
            ]]}
            tg_photo(img, f"🧡 [Printables]\n{title}", kb)
    except Exception as e:
        tg_text(f"❌ Printables: {e}")

#### 3. Cults3D ####
def cults3d_latest():
    try:
        resp = requests.get("https://cults3d.com/en/3d-model/new", timeout=20)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select('a.card-product__link')[:2]
        for a in cards:
            url = "https://cults3d.com" + a['href']
            title = a.find("span", class_="card-product__name").text.strip()
            img = a.find("img")['src']
            kb = {"inline_keyboard": [[
                {"text": "عرض على Cults3D", "url": url}
            ]]}
            tg_photo(img, f"💜 [Cults3D]\n{title}", kb)
    except Exception as e:
        tg_text(f"❌ Cults3D: {e}")

def worker():
    while True:
        try:
            # أحدث التصميمات من كل موقع
            thingiverse_latest()
            printables_latest()
            cults3d_latest()
            # التصاميم الرائجة من Thingiverse فقط (API متاح)
            thingiverse_popular()
        except Exception as e:
            tg_text(f"❌ Worker Error: {e}\n{traceback.format_exc(limit=2)}")
        time.sleep(180)  # كل 3 دقائق

if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))