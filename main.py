#!/usr/bin/env python3

import os import time import json import traceback import pickle from threading import Thread

import cloudscraper import requests from bs4 import BeautifulSoup from flask import Flask

Telegram credentials and Thingiverse API token

BOT_TOKEN = os.getenv("BOT_TOKEN") CHAT_ID   = os.getenv("CHAT_ID") APP_TOKEN = os.getenv("APP_TOKEN")  # Only for Thingiverse PORT      = int(os.getenv("PORT", "10000"))

assert BOT_TOKEN and CHAT_ID, "Missing BOT_TOKEN or CHAT_ID"

Flask app for keep-alive

app = Flask(name) @app.route("/") def index(): return "Bot is running."

SELF_URL = os.getenv("SELF_URL") if SELF_URL: def keep_alive(): while True: try: requests.get(SELF_URL) except: pass time.sleep(240)

Create a scraper session

scraper = cloudscraper.create_scraper( browser={"browser": "firefox", "platform": "linux", "desktop": True} ) TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

State persistence

STATE_FILE = "last_ids.pkl" last_ids = { "thingiverse_newest": None, "printables":        None, "makerworld":        None, "cults3d":           None, }

def load_state(): global last_ids if os.path.exists(STATE_FILE): with open(STATE_FILE, "rb") as f: last_ids = pickle.load(f)

def save_state(): with open(STATE_FILE, "wb") as f: pickle.dump(last_ids, f)

Telegram functions

def tg_photo(photo_url, caption, view_url, dl_url): kb = {"inline_keyboard": [[ {"text": "🔗 View",         "url": view_url}, {"text": "⬇️ Download STL", "url": dl_url}, {"text": "📤 Share",        "url": f"https://t.me/share/url?url={view_url}"} ]]} payload = { "chat_id": CHAT_ID, "photo":   photo_url, "caption": caption, "reply_markup": json.dumps(kb, ensure_ascii=False) } scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt): scraper.post( f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"}, timeout=10 )

Thingiverse API

API_ROOT = "https://api.thingiverse.com" def newest_thingiverse(): if not APP_TOKEN: return [] url = f"{API_ROOT}/newest/things" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() return r.json()

def first_file_id(thing_id): url = f"{API_ROOT}/things/{thing_id}/files" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() files = r.json() return files[0]["id"] if files and isinstance(files, list) else None

RSS fetch via BeautifulSoup XML parser

def fetch_rss_items_bs(url): try: r = scraper.get(url, timeout=20) r.raise_for_status() soup = BeautifulSoup(r.text, 'xml') return soup.find_all('item') except: return []

Process any RSS feed

def process_rss(name, url, icon): items = fetch_rss_items_bs(url) if not items: return # extract links and titles links = [i.link.text.strip() for i in items] # determine new ones if last_ids.get(name) in links: idx = links.index(last_ids[name]) new_links = links[:idx] else: new_links = links # send in chronological order for link in reversed(new_links): title = next((i.title.text.strip() for i in items if i.link.text.strip() == link), link) tg_text(f"{icon} <b>[{name.capitalize()}]</b> <a href="{link}">{title}</a>") # update state last_ids[name] = links[0] save_state()

Main worker

def worker(): load_state() while True: try: # Thingiverse for thing in newest_thingiverse(): if thing.get("id") == last_ids.get("thingiverse_newest"): break title   = thing.get("name", "Thing") pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}" thumb   = thing.get("thumbnail") or thing.get("preview_image") or "" file_id = first_file_id(thing['id']) dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url) if newest_thingiverse(): last_ids["thingiverse_newest"] = newest_thingiverse()[0].get("id") save_state()

# RSS-based sources
        process_rss('printables',  'https://www.printables.com/rss', '🖨️')
        process_rss('makerworld',  'https://makerworld.com/feed',     '🔧')
        process_rss('cults3d',     'https://cults3d.com/en/feed',    '🎨')

    except Exception:
        traceback.print_exc(limit=1)
    time.sleep(120)

if name == 'main': Thread(target=worker,    daemon=True).start() if SELF_URL: Thread(target=keep_alive, daemon=True).start() app.run(host='0.0.0.0', port=PORT)

