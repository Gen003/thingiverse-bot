#!/usr/bin/env python3
import os
import time
import json
import traceback
import pickle
import requests
from bs4 import BeautifulSoup
from threading import Thread
from flask import Flask

# ───── متغيرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")
PORT      = int(os.getenv("PORT", "10000"))

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "Missing environment variables."

# ───── Flask ─────
app = Flask(__name__)
@app.route("/")
def index():
    return "Bot is running."

SELF_URL = os.getenv("SELF_URL", "https://thingiverse-bot.onrender.com")
def keep_alive():
    while True:
        try:
            requests.get(SELF_URL)
        except:
            pass
        time.sleep(240)

# ───── إعداد Scraper ─────
scraper = requests.Session()
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ───── حفظ واسترجاع الحالة ─────
STATE_FILE = "last_ids.pkl"
last_ids = {
    "thingiverse_newest": None,
    "printables":        None,
    "makerworld":        None,
    "cults3d":           None,
    "myminifactory":     None,
    "thangs":            None,
    "pinshape":          None,
}

def load_state():
    global last_ids
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            last_ids = pickle.load(f)

def save_state():
    with open(STATE_FILE, "wb") as f:
        pickle.dump(last_ids, f)

# ───── وظائف Telegram ─────
def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str):
    kb = {"inline_keyboard": [[
        {"text": "🔗 View",         "url": view_url},
        {"text": "⬇️ Download STL", "url": dl_url},
        {"text": "📤 Share",        "url": f"https://t.me/share/url?url={view_url}"}
    ]]}
    payload = {
        "chat_id": CHAT_ID,
        "photo":   photo_url,
        "caption": caption,
        "reply_markup": json.dumps(kb, ensure_ascii=False)
    }
    scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str):
    scraper.post(
        f"{TG_ROOT}/sendMessage",
        data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"},
        timeout=10
    )

# ───── Thingiverse API ─────
API_ROOT = "https://api.thingiverse.com"
def newest_thingiverse():
    url = f"{API_ROOT}/newest/things"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    return r.json()

def first_file_id(thing_id: int):
    url = f"{API_ROOT}/things/{thing_id}/files"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    files = r.json()
    return files[0]["id"] if isinstance(files, list) and files else None

# ───── وظائف RSS و Scraping ─────
def fetch_rss_items(url: str):
    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.find_all("item")
        return items
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return []

def fetch_printables_items():
    return fetch_rss_items("https://www.printables.com/rss")

def fetch_makerworld_items():
    return fetch_rss_items("https://makerworld.com/feed")

def fetch_cults_items():
    return fetch_rss_items("https://cults3d.com/en/feed")

def fetch_myminifactory_items():
    url = "https://www.myminifactory.com/search/?query=&sort=newest"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.find_all("a", href=True)
    return [{"title": a.get_text(strip=True), "link": f"https://www.myminifactory.com{a['href']}"} for a in items]

def fetch_thangs_items():
    url = "https://thangs.com/discover"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.find_all("a", href=True)
    return [{"title": a.get_text(strip=True), "link": f"https://thangs.com{a['href']}"} for a in items]

def fetch_pinshape_items():
    url = "https://pinshape.com/discover?sort=newest"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.find_all("a", href=True)
    return [{"title": a.get_text(strip=True), "link": f"https://pinshape.com{a['href']}"} for a in items]

# ───── العامل الرئيسي (Worker) ─────
def worker():
    global last_ids
    load_state()
    while True:
        try:
            # Thingiverse
            for thing in newest_thingiverse():
                if thing["id"] == last_ids["thingiverse_newest"]:
                    break
                title = thing.get("name", "Thing")
                pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                thumb = thing.get("thumbnail") or thing.get("preview_image") or ""
                file_id = first_file_id(thing["id"])
                dl_url = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url)
                last_ids["thingiverse_newest"] = thing["id"]
                save_state()

            # Generic RSS
            for name, fetcher in [
                ("printables", fetch_printables_items),
                ("makerworld", fetch_makerworld_items),
                ("cults3d", fetch_cults_items),
            ]:
                for item in fetcher():
                    title = item.find("title").text
                    link = item.find("link").text
                    tg_text(f"🔗 <b>[{name.capitalize()}]</b> <a href=\\\"{link}\\\">{title}</a>")
                    last_ids[name] = link
                    save_state()

            # Scraped sources
            for name, fetcher in [
                ("myminifactory", fetch_myminifactory_items),
                ("thangs", fetch_thangs_items),
                ("pinshape", fetch_pinshape_items),
            ]:
                for item in fetcher():
                    if item["link"] == last_ids[name]:
                        break
                    tg_text(f"🌐 <b>[{name.capitalize()}]</b> <a href=\\\"{item['link']}\\\">{item['title']}</a>")
                    last_ids[name] = item["link"]
                    save_state()

        except Exception:
            traceback.print_exc(limit=1)

        time.sleep(120)

if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)