-- coding: utf-8 --

""" Thingiverse → Telegram  ❚ د. إيرك 2025 يرسل كل نموذج جديد فور رفعه من المنصات التالية: - Thingiverse (API) - Printables.com (RSS) - MakerWorld.com (RSS) - Cults3D (RSS) - MyMiniFactory (Scraping) - Thangs.com (Scraping) - Pinshape (Scraping) """ import os import time import json import traceback import pickle import xml.etree.ElementTree as ET from threading import Thread

import cloudscraper import requests from flask import Flask from bs4 import BeautifulSoup

#───── متغيّرات البيئة ─────

BOT_TOKEN = os.getenv("BOT_TOKEN") CHAT_ID   = os.getenv("CHAT_ID") APP_TOKEN = os.getenv("APP_TOKEN") PORT      = int(os.getenv("PORT", "10000"))

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), 
"🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN يجب تعيينها!"

───── Flask ─────

app = Flask(name) @app.route("/") def index(): return "✅ Thingiverse-Bot is running."

───── Self Ping للحفاظ على الحياة ─────

SELF_URL = os.getenv("SELF_URL", "https://thingiverse-bot.onrender.com") def keep_alive(): while True: try: requests.get(SELF_URL) except: pass time.sleep(240)

───── إعداد Scraper للطلبات ─────

scraper = cloudscraper.create_scraper( browser={"browser": "firefox", "platform": "linux", "desktop": True} ) TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

───── حفظ واسترجاع الحالة ─────

STATE_FILE = "last_ids.pkl" last_ids = { "thingiverse_newest": None, "printables":        None, "makerworld":        None, "cults3d":           None, "myminifactory":     None, "thangs":            None, "pinshape":          None, }

def load_state(): global last_ids if os.path.exists(STATE_FILE): with open(STATE_FILE, "rb") as f: last_ids = pickle.load(f)

def save_state(): with open(STATE_FILE, "wb") as f: pickle.dump(last_ids, f)

───── وظائف Telegram ─────

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str): kb = {"inline_keyboard": [[ {"text": "🔗 View",         "url": view_url}, {"text": "⬇️ Download STL", "url": dl_url}, {"text": "📤 Share",        "url": f"https://t.me/share/url?url={view_url}"} ]]} payload = { "chat_id": CHAT_ID, "photo":   photo_url, "caption": caption, "reply_markup": json.dumps(kb, ensure_ascii=False) } scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str): scraper.post( f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"}, timeout=10 )

───── Thingiverse API ─────

API_ROOT = "https://api.thingiverse.com" def newest_thingiverse(): url = f"{API_ROOT}/newest/things" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() return r.json()

def first_file_id(thing_id: int): url = f"{API_ROOT}/things/{thing_id}/files" r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20) r.raise_for_status() files = r.json() return files[0]["id"] if isinstance(files, list) and files else None

───── RSS Fetchers ─────

def fetch_rss_items(url: str, source: str): try: r = scraper.get(url, timeout=20) r.raise_for_status() root = ET.fromstring(r.text) items = root.findall("./channel/item") if not items: print(f"🔴 [{source}] لا توجد عناصر في RSS") return items except Exception as e: print(f"🔴 [{source}] فشل تحميل RSS: {e}") return []

def fetch_printables_items(): return fetch_rss_items("https://www.printables.com/rss", "Printables")

def fetch_makerworld_items(): return fetch_rss_items("https://makerworld.com/feed", "MakerWorld")

def fetch_cults_items(): return fetch_rss_items("https://cults3d.com/en/feed", "Cults3D")

───── HTML Scraping Fetchers ─────

def fetch_myminifactory_items(): url = "https://www.myminifactory.com/search/?query=&sort=newest" r = scraper.get(url, timeout=20) r.raise_for_status() soup = BeautifulSoup(r.text, "html.parser") items = [] for a in soup.select("a[href^='/object/']"): title = a.get("title") or a.get_text(strip=True) link  = "https://www.myminifactory.com" + a["href"] items.append({"title": title, "link": link}) if not items: print("🔴 [MyMiniFactory] لا توجد عناصر") return items

def fetch_thangs_items(): url = "https://thangs.com/discover" r = scraper.get(url, timeout=20) r.raise_for_status() soup = BeautifulSoup(r.text, "html.parser") items = [] for a in soup.select("a[href^='/model/']"): title = a.get_text(strip=True) link  = "https://thangs.com" + a["href"] items.append({"title": title, "link": link}) if not items: print("🔴 [Thangs] لا توجد عناصر") return items

def fetch_pinshape_items(): url = "https://pinshape.com/discover?sort=newest" r = scraper.get(url, timeout=20) r.raise_for_status() soup = BeautifulSoup(r.text, "html.parser") items = [] for card in soup.select("div.card-list__item"): a = card.find("a", href=True) if not a: continue title = a.get("title") or card.find("h3").get_text(strip=True) link  = "https://pinshape.com" + a["href"] items.append({"title": title, "link": link}) if not items: print("🔴 [Pinshape] لا توجد عناصر") return items

───── العامل الرئيسي (Worker) ─────

def worker(): global last_ids load_state() while True: try: # ── Thingiverse things = newest_thingiverse() new_items = [] for thing in things: if thing["id"] == last_ids["thingiverse_newest"]: break new_items.append(thing) if new_items: for thing in reversed(new_items): title   = thing.get("name", "Thing") pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}" thumb   = thing.get("thumbnail") or thing.get("preview_image") or "" file_id = first_file_id(thing["id"]) dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url) last_ids["thingiverse_newest"] = new_items[0]["id"] save_state()

# ── Printables
        items = fetch_printables_items()
        new_items = []
        for item in items:
            link = item.find("link").text
            if link == last_ids["printables"]:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                title = item.find("title").text
                link  = item.find("link").text
                tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{link}\">{title}</a>")
            last_ids["printables"] = new_items[0].find("link").text
            save_state()

        # ── MakerWorld
        items = fetch_makerworld_items()
        new_items = []
        for item in items:
            link = item.find("link").text
            if link == last_ids["makerworld"]:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                title = item.find("title").text
                link  = item.find("link").text
                tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{link}\">{title}</a>")
            last_ids["makerworld"] = new_items[0].find("link").text
            save_state()

        # ── Cults3D
        items = fetch_cults_items()
        new_items = []
        for item in items:
            link = item.find("link").text
            if link == last_ids["cults3d"]:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                title = item.find("title").text
                link  = item.find("link").text
                tg_text(f"🎨 <b>[Cults3D]</b> <a href=\"{link}\">{title}</a>")
            last_ids["cults3d"] = new_items[0].find("link").text
            save_state()

        # ── MyMiniFactory
        items = fetch_myminifactory_items()
        new_items = []
        for item in items:
            if item['link'] == last_ids['myminifactory']:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                tg_text(f"🛠️ <b>[MyMiniFactory]</b> <a href=\"{item['link']}\">{item['title']}</a>")
            last_ids['myminifactory'] = new_items[0]['link']
            save_state()

        # ── Thangs.com
        items = fetch_thangs_items()
        new_items = []
        for item in items:
            if item['link'] == last_ids['thangs']:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                tg_text(f"🔎 <b>[Thangs]</b> <a href=\"{item['link']}\">{item['title']}</a>")
            last_ids['thangs'] = new_items[0]['link']
            save_state()

        # ── Pinshape
        items = fetch_pinshape_items()
        new_items = []
        for item in items:
            if item['link'] == last_ids['pinshape']:
                break
            new_items.append(item)
        if new_items:
            for item in reversed(new_items):
                tg_text(f"📐 <b>[Pinshape]</b> <a href=\"{item['link']}\">{item['title']}</a>")
            last_ids['pinshape'] = new_items[0]['link']
            save_state()

    except Exception:
        traceback.print_exc(limit=1)

    time.sleep(120)

───── تشغيل مقدّس ─────

if name == "main": Thread(target=worker, daemon=True).start() Thread(target=keep_alive, daemon=True).start() app.run(host="0.0.0.0", port=PORT)

