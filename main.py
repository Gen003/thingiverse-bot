#!/usr/bin/env python3

import os import time import json import traceback import pickle from threading import Thread import xml.etree.ElementTree as ET

import cloudscraper import requests from flask import Flask from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN") CHAT_ID   = os.getenv("CHAT_ID") APP_TOKEN = os.getenv("APP_TOKEN") PORT      = int(os.getenv("PORT", "10000"))

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "Missing environment variables."

app = Flask(name) @app.route("/") def index(): return "Bot is running."

SELF_URL = os.getenv("SELF_URL", "https://thingiverse-bot.onrender.com") def keep_alive(): while True: try: requests.get(SELF_URL) except: pass time.sleep(240)

scraper = cloudscraper.create_scraper( browser={"browser": "firefox", "platform": "linux", "desktop": True} ) TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

STATE_FILE = "last_ids.pkl" last_ids = { "thingiverse_newest": None, "printables":        None, "makerworld":        None, "cults3d":           None, }

def load_state(): global last_ids if os.path.exists(STATE_FILE): with open(STATE_FILE, "rb") as f: last_ids = pickle.load(f)

def save_state(): with open(STATE_FILE, "wb") as f: pickle.dump(last_ids, f)

def tg_text(txt: str): scraper.post( f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"}, timeout=10 )

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str): kb = {"inline_keyboard": [[ {"text": "🔗 View",         "url": view_url}, {"text": "⬇️ Download STL", "url": dl_url}, {"text": "📤 Share",        "url": f"https://t.me/share/url?url={view_url}"} ]]} payload = { "chat_id": CHAT_ID, "photo":   photo_url, "caption": caption, "reply_markup": json.dumps(kb, ensure_ascii=False) } scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

Thingiverse only – keep untouched

API_ROOT = "https://api.thingiverse.com" def newest_thingiverse(): url = f"{API_ROOT}/newest/things" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() return r.json()

def first_file_id(thing_id: int): url = f"{API_ROOT}/things/{thing_id}/files" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() files = r.json() return files[0]["id"] if isinstance(files, list) and files else None

def fetch_rss_items(url: str): try: headers = {"User-Agent": "Mozilla/5.0"} r = scraper.get(url, headers=headers, timeout=20) r.raise_for_status() root = ET.fromstring(r.text) return root.findall("./channel/item") except: return []

def fetch_printables_items(): return fetch_rss_items("https://www.printables.com/rss")

def fetch_makerworld_items(): return fetch_rss_items("https://makerworld.com/feed")

def fetch_cults_items(): return fetch_rss_items("https://cults3d.com/en/feed")

def worker(): global last_ids load_state() while True: try: # Thingiverse only things = newest_thingiverse() new_items = [] for thing in things: if thing["id"] == last_ids["thingiverse_newest"]: break new_items.append(thing) if new_items: for thing in reversed(new_items): title   = thing.get("name", "Thing") pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}" thumb   = thing.get("thumbnail") or thing.get("preview_image") or "" file_id = first_file_id(thing["id"]) dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url) last_ids["thingiverse_newest"] = new_items[0]["id"] save_state()

# RSS-based sources
        for name, fetcher, icon in [
            ("printables", fetch_printables_items, "🖨️"),
            ("makerworld", fetch_makerworld_items, "🔧"),
            ("cults3d", fetch_cults_items, "🎨"),
        ]:
            items = fetcher()
            new_items = []
            for item in items:
                link = item.find("link").text.strip()
                if link == last_ids[name]:
                    break
                new_items.append(item)
            if new_items:
                for item in reversed(new_items):
                    title = item.find("title").text.strip()
                    link  = item.find("link").text.strip()
                    tg_text(f"{icon} <b>[{name.capitalize()}]</b> <a href=\"{link}\">{title}</a>")
                last_ids[name] = new_items[0].find("link").text.strip()
                save_state()

    except Exception:
        traceback.print_exc(limit=1)

    time.sleep(120)

if name == "main": Thread(target=worker, daemon=True).start() Thread(target=keep_alive, daemon=True).start() app.run(host="0.0.0.0", port=PORT)

