# -*- coding: utf-8 -*-
"""
main.py
Ultimate STL Feeder → Telegram  ❚  د. إيرك 2025
• جلب تلقائي للتصاميم الجديدة والرائجة كل 3 دقائق
• المواقع: Thingiverse, Printables, Cults3D, MakerWorld
"""

import os
import time
import json
import requests
import cloudscraper
from threading import Thread
from flask import Flask
from bs4 import BeautifulSoup

# ───── متغيّرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
SELF_URL  = os.getenv("SELF_URL", "https://your-app.onrender.com")  # عدّل إلى رابط تطبيقك

assert BOT_TOKEN and CHAT_ID, "🔴 تأكد من ضبط BOT_TOKEN و CHAT_ID في المتغيرات البيئية"

# ───── تهيئة Flask ─────
app = Flask(__name__)
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_text(text):
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(f"{TG_API}/sendMessage", data=data)

def tg_photo(photo_url, caption, keyboard):
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "reply_markup": json.dumps(keyboard, ensure_ascii=False)
    }
    requests.post(f"{TG_API}/sendPhoto", data=payload)

# ───── مسار صحة التشغيل ─────
@app.route("/", methods=["GET"])
def index():
    return "✅ STL-Bot is running.", 200

# ───── مجموعات لتفادي التكرار ─────
sent_new      = {"thingiverse": set(), "printables": set(), "cults3d": set(), "makerworld": set()}
sent_trending = {"thingiverse": set(), "printables": set(), "cults3d": set(), "makerworld": set()}

# ───── 1. Thingiverse: جديد + رائج ─────
def thingiverse_new():
    scraper = cloudscraper.create_scraper()
    url = "https://www.thingiverse.com/explore/newest/"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for c in soup.select('.ThingCard')[:5]:
        a   = c.select_one('.ThingCard__title a')
        tid = a['href'].split('/')[-1]
        if tid in sent_new["thingiverse"]: continue
        sent_new["thingiverse"].add(tid)
        title = a.text.strip()
        link  = "https://www.thingiverse.com" + a['href']
        img   = c.select_one('img.ThingCard__img')
        src   = img.get('data-src') or img.get('src')
        kb    = {"inline_keyboard":[[
            {"text":"عرض","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(src, f"🌍 [Thingiverse • New]\n{title}", kb)

def thingiverse_trending():
    scraper = cloudscraper.create_scraper()
    url = "https://www.thingiverse.com/explore/popular/"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for c in soup.select('.ThingCard')[:5]:
        a   = c.select_one('.ThingCard__title a')
        tid = a['href'].split('/')[-1]
        if tid in sent_trending["thingiverse"]: continue
        sent_trending["thingiverse"].add(tid)
        title = a.text.strip()
        link  = "https://www.thingiverse.com" + a['href']
        img   = c.select_one('img.ThingCard__img')
        src   = img.get('data-src') or img.get('src')
        kb    = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(src, f"🔥 [Thingiverse • Trending]\n{title}", kb)

# ───── 2. Printables: جديد + رائج ─────
def printables_new():
    scraper = cloudscraper.create_scraper()
    url = "https://www.printables.com/model"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a[data-cy="model-card-link"]')[:5]:
        href = a['href']
        if href in sent_new["printables"]: continue
        sent_new["printables"].add(href)
        title = a.select_one(".card__title").text.strip()
        link  = "https://www.printables.com" + href
        img   = a.find("img")['src']
        kb    = {"inline_keyboard":[[
            {"text":"عرض","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(img, f"🧡 [Printables • New]\n{title}", kb)

def printables_trending():
    scraper = cloudscraper.create_scraper()
    url = "https://www.printables.com/popular"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a[data-cy="model-card-link"]')[:5]:
        href = a['href']
        if href in sent_trending["printables"]: continue
        sent_trending["printables"].add(href)
        title = a.select_one(".card__title").text.strip()
        link  = "https://www.printables.com" + href
        img   = a.find("img")['src']
        kb    = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(img, f"🔥 [Printables • Trending]\n{title}", kb)

# ───── 3. Cults3D: جديد + رائج ─────
def cults3d_new():
    scraper = cloudscraper.create_scraper()
    url = "https://cults3d.com/en/3d-model/new"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a.card-product__link')[:5]:
        href = a['href']
        if href in sent_new["cults3d"]: continue
        sent_new["cults3d"].add(href)
        title = a.select_one(".card-product__name").text.strip()
        link  = "https://cults3d.com" + href
        img   = a.find("img")['src']
        kb    = {"inline_keyboard":[[
            {"text":"عرض","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(img, f"💜 [Cults3D • New]\n{title}", kb)

def cults3d_trending():
    scraper = cloudscraper.create_scraper()
    url = "https://cults3d.com/en/3d-model/popular"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a.card-product__link')[:5]:
        href = a['href']
        if href in sent_trending["cults3d"]: continue
        sent_trending["cults3d"].add(href)
        title = a.select_one(".card-product__name").text.strip()
        link  = "https://cults3d.com" + href
        img   = a.find("img")['src']
        kb    = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(img, f"🔥 [Cults3D • Trending]\n{title}", kb)

# ───── 4. MakerWorld: جديد + رائج ─────
def makerworld_new():
    resp = requests.get("https://makerworld.com/", timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('article h2.entry-title a')[:5]:
        href = a['href']
        if href in sent_new["makerworld"]: continue
        sent_new["makerworld"].add(href)
        title = a.text.strip()
        img   = a.find_parent('article').find('img')
        if img:
            kb = {"inline_keyboard":[[{"text":"عرض","url":href}]]}
            tg_photo(img['src'], f"🛠️ [MakerWorld • New]\n{title}", kb)
        else:
            tg_text(f"🛠️ [MakerWorld • New]\n{title}\n{href}")

def makerworld_trending():
    resp = requests.get("https://makerworld.com/", timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('section.popular-posts li a')[:5]:
        href = a['href']
        if href in sent_trending["makerworld"]: continue
        sent_trending["makerworld"].add(href)
        title = a.text.strip()
        tg_text(f"⚡ [MakerWorld • Trending]\n{title}\n{href}")

# ───── العامل الدوري ─────
def periodic_worker():
    while True:
        try:
            thingiverse_new()
            thingiverse_trending()
            printables_new()
            printables_trending()
            cults3d_new()
            cults3d_trending()
            makerworld_new()
            makerworld_trending()
        except Exception as e:
            tg_text(f"❌ Worker Error:\n{e}")
        time.sleep(180)  # 3 دقائق

# ───── إبقاء التطبيق نشط ─────
def keep_alive():
    while True:
        try: requests.get(SELF_URL)
        except: pass
        time.sleep(240)  # 4 دقائق

# ───── بدء البوت ─────
if __name__ == "__main__":
    Thread(target=keep_alive,   daemon=True).start()
    Thread(target=periodic_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))