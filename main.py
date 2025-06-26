#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Main bot file: monitors several 3D-model repositories and pushes new items to Telegram

import os
import time
import os import time import json import pickle import traceback from threading import Thread

import requests import cloudscraper from bs4 import BeautifulSoup from flask import Flask

--- required environment variables ---

BOT_TOKEN = os.getenv("BOT_TOKEN")          # Telegram bot token CHAT_ID   = os.getenv("CHAT_ID")            # Telegram chat/channel id (use negative id for channels) APP_TOKEN = os.getenv("APP_TOKEN")          # Thingiverse API token (optional but recommended) PORT      = int(os.getenv("PORT", "10000")) SELF_URL  = os.getenv("SELF_URL")           # public url for keep‑alive (optional)

if not BOT_TOKEN or not CHAT_ID: raise SystemExit("BOT_TOKEN and CHAT_ID must be set")

# --- flask app for keep-alive ---


app = Flask(name) @app.route("/") def index(): return "ok"

if SELF_URL: def keep_alive(): while True: try: requests.get(SELF_URL, timeout=10) except Exception: pass time.sleep(240)

--- http sessions ---

scraper = cloudscraper.create_scraper( browser={"browser": "firefox", "platform": "linux", "desktop": True} ) TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

--- persistent state ---

STATE_FILE = "last_ids.pkl" last_ids = { "thingiverse_newest": None, "printables":        None, "makerworld":        None, "cults3d":           None, "myminifactory":     None, "thangs":            None, "pinshape":          None, }

def load_state(): global last_ids if os.path.isfile(STATE_FILE): with open(STATE_FILE, "rb") as f: last_ids = pickle.load(f)

def save_state(): with open(STATE_FILE, "wb") as f: pickle.dump(last_ids, f)

--- telegram helpers ---

def tg_text(html: str): scraper.post( f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": html, "parse_mode": "HTML"}, timeout=15, )

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str): kb = {"inline_keyboard": [[ {"text": "🔗 View", "url": view_url}, {"text": "⬇️ Download", "url": dl_url}, {"text": "📤 Share", "url": f"https://t.me/share/url?url={view_url}"}, ]]} payload = { "chat_id": CHAT_ID, "photo": photo_url, "caption": caption, "reply_markup": json.dumps(kb, ensure_ascii=False), } scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=20)

--- Thingiverse (official API) ---

API_ROOT = "https://api.thingiverse.com"

def newest_thingiverse(): if not APP_TOKEN: return [] r = scraper.get(f"{API_ROOT}/newest/things", params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() return r.json()

def first_file_id(thing_id: int): r = scraper.get(f"{API_ROOT}/things/{thing_id}/files", params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() files = r.json() return files[0]["id"] if isinstance(files, list) and files else None

--- generic rss fetch (BeautifulSoup xml) ---

def rss_items(url: str): try: r = scraper.get(url, timeout=20) r.raise_for_status() soup = BeautifulSoup(r.text, "xml") return soup.find_all("item") except Exception: return []

--- site‑specific fetchers ---

def items_printables(): return rss_items("https://www.printables.com/rss")

def items_makerworld(): return rss_items("https://makerworld.com/feed")

def items_cults(): return rss_items("https://cults3d.com/en/feed")

simple html scrapers for sites without rss

def items_myminifactory(): url = "https://www.myminifactory.com/search/?query=&sort=newest" r = scraper.get(url, timeout=20) soup = BeautifulSoup(r.text, "html.parser") data = [] for a in soup.select("a[href^='/object/']")[:40]: title = a.get("title") or a.get_text(strip=True) link = "https://www.myminifactory.com" + a["href"] data.append({"title": title, "link": link}) return data

def items_thangs(): url = "https://thangs.com/discover" r = scraper.get(url, timeout=20) soup = BeautifulSoup(r.text, "html.parser") data = [] for a in soup.select("a[href^='/model/']")[:40]: title = a.get_text(strip=True) link = "https://thangs.com" + a["href"] data.append({"title": title, "link": link}) return data

def items_pinshape(): url = "https://pinshape.com/discover?sort=newest" r = scraper.get(url, timeout=20) soup = BeautifulSoup(r.text, "html.parser") data = [] for a in soup.select("a[href^='/items/']")[:40]: title = a.get_text(strip=True) link = "https://pinshape.com" + a["href"] data.append({"title": title, "link": link}) return data

--- main loop ---

def worker(): load_state() while True: try: # Thingiverse for thing in newest_thingiverse(): if thing["id"] == last_ids.get("thingiverse_newest"): break title = thing.get("name", "Thing") url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}" thumb = thing.get("thumbnail") or thing.get("preview_image") or "" file_id = first_file_id(thing["id"]) dl_url = f"https://www.thingiverse.com/download:{file_id}" if file_id else url tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", url, dl_url) if newest_thingiverse(): last_ids["thingiverse_newest"] = newest_thingiverse()[0]["id"] save_state()

# RSS sources
        for name, fetch, icon in [
            ("printables", items_printables, "🖨️"),
            ("makerworld", items_makerworld, "🔧"),
            ("cults3d", items_cults, "🎨"),
        ]:
            items = fetch()
            if not items:
                continue
            links = [i.link.text.strip() for i in items]
            if last_ids.get(name) in links:
                idx = links.index(last_ids[name])
                links = links[:idx]
            for link in reversed(links):
                title = next(i.title.text.strip() for i in items if i.link.text.strip() == link)
                tg_text(f"{icon} <b>[{name.capitalize()}]</b> <a href=\"{link}\">{title}</a>")
            if links:
                last_ids[name] = links[0]
                save_state()

        # Scraped sources
        for name, fetch, icon in [
            ("myminifactory", items_myminifactory, "🛠️"),
            ("thangs",        items_thangs,        "🔎"),
            ("pinshape",      items_pinshape,      "📐"),
        ]:
            items = fetch()
            if not items:
                continue
            links = [i["link"] for i in items]
            if last_ids.get(name) in links:
                idx = links.index(last_ids[name])
                links = links[:idx]
            for link in reversed(links):
                title = next(d["title"] for d in items if d["link"] == link)
                tg_text(f"{icon} <b>[{name.capitalize()}]</b> <a href=\"{link}\">{title}</a>")
            if links:
                last_ids[name] = links[0]
                save_state()

    except Exception:
        traceback.print_exc(limit=1)

    time.sleep(120)

--- start threads ---

if name == "main": Thread(target=worker, daemon=True).start() if SELF_URL: Thread(target=keep_alive, daemon=True).start() app.run(host="0.0.0.0", port=PORT)

