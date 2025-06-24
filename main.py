# -*- coding: utf-8 -*-
"""
Ultimate STL Feeder → Telegram  ❚  د. إيرك 2025
• تحديث تلقائي (Newest & Trending every 3min)
• أمر /search لجلب أفضل 10 تصميمات
• المصدر: Thingiverse, Printables, Cults3D, MakerWorld
"""

import os, time, json, traceback, requests, cloudscraper
from datetime import datetime
from threading import Thread
from flask import Flask, request
from bs4 import BeautifulSoup
from urllib.parse import quote

# ───── متغيّرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
assert BOT_TOKEN and CHAT_ID, "🔴 BOT_TOKEN / CHAT_ID must be set!"

SELF_URL = os.getenv("SELF_URL", "https://thingiverse-bot.onrender.com")
app = Flask(__name__)
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ───── حالة الإرسال لتفادي التكرار ─────
sent_thingiverse_new       = set()
sent_thingiverse_trending  = set()
sent_printables_new        = set()
sent_printables_trending   = set()
sent_cults_new             = set()
sent_cults_trending        = set()
sent_maker_new             = set()
sent_maker_trending        = set()

# ───── وظائف Telegram ─────
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

# ───── إبقاء البوت نشط ─────
def keep_alive():
    while True:
        try: requests.get(SELF_URL)
        except: pass
        time.sleep(240)  # كل 4 دقائق

# ───── 1. Thingiverse Scraping ─────
def thingiverse_latest_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://www.thingiverse.com/explore/newest/"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('.ThingCard')[:5]
    for c in cards:
        a = c.select_one('.ThingCard__title a')
        href = a['href']
        tid = href.split('/')[-1]
        if tid in sent_thingiverse_new: continue
        sent_thingiverse_new.add(tid)
        title = a.text.strip()
        link  = "https://www.thingiverse.com" + href
        img   = c.select_one('img.ThingCard__img')
        src   = img.get('data-src') or img.get('src')
        kb = {"inline_keyboard":[[
            {"text":"عرض على Thingiverse","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(src, f"🌍 [Thingiverse • New]\n{title}", kb)

def thingiverse_trending_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://www.thingiverse.com/explore/popular/"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('.ThingCard')[:5]
    for c in cards:
        a = c.select_one('.ThingCard__title a')
        href = a['href']
        tid = href.split('/')[-1]
        if tid in sent_thingiverse_trending: continue
        sent_thingiverse_trending.add(tid)
        title = a.text.strip()
        link  = "https://www.thingiverse.com" + href
        img   = c.select_one('img.ThingCard__img')
        src   = img.get('data-src') or img.get('src')
        kb = {"inline_keyboard":[[{"text":"عرض على Thingiverse","url":link}]]}
        tg_photo(src, f"🔥 [Thingiverse • Trending]\n{title}", kb)

# ───── 2. Printables Scraping ─────
def printables_latest_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://www.printables.com/model"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('a[data-cy="model-card-link"]')[:5]
    for a in cards:
        href  = a['href']
        pid   = href
        if pid in sent_printables_new: continue
        sent_printables_new.add(pid)
        link  = "https://www.printables.com" + href
        title = a.select_one(".card__title").text.strip()
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[
            {"text":"عرض على Printables","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(img, f"🧡 [Printables • New]\n{title}", kb)

def printables_trending_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://www.printables.com/popular"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('a[data-cy="model-card-link"]')[:5]
    for a in cards:
        href  = a['href']
        pid   = href
        if pid in sent_printables_trending: continue
        sent_printables_trending.add(pid)
        link  = "https://www.printables.com" + href
        title = a.select_one(".card__title").text.strip()
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[
            {"text":"عرض على Printables","url":link}
        ]]}
        tg_photo(img, f"🔥 [Printables • Trending]\n{title}", kb)

# ───── 3. Cults3D Scraping ─────
def cults_latest_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://cults3d.com/en/3d-model/new"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('a.card-product__link')[:5]
    for a in cards:
        href = a['href']
        cid  = href
        if cid in sent_cults_new: continue
        sent_cults_new.add(cid)
        link  = "https://cults3d.com" + href
        title = a.select_one(".card-product__name").text.strip()
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[
            {"text":"عرض على Cults3D","url":link},
            {"text":"تحميل STL","url":link}
        ]]}
        tg_photo(img, f"💜 [Cults3D • New]\n{title}", kb)

def cults_trending_scrape():
    scraper = cloudscraper.create_scraper()
    url = "https://cults3d.com/en/3d-model/popular"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select('a.card-product__link')[:5]
    for a in cards:
        href = a['href']
        cid  = href
        if cid in sent_cults_trending: continue
        sent_cults_trending.add(cid)
        link  = "https://cults3d.com" + href
        title = a.select_one(".card-product__name").text.strip()
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[{"text":"عرض على Cults3D","url":link}]]}
        tg_photo(img, f"🔥 [Cults3D • Trending]\n{title}", kb)

# ───── 4. MakerWorld Scraping ─────
def maker_latest_scrape():
    url = "https://makerworld.com/"
    resp = requests.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('article h2.entry-title a')[:5]
    for a in items:
        href = a['href']
        mid  = href
        if mid in sent_maker_new: continue
        sent_maker_new.add(mid)
        title = a.text.strip()
        img = a.find_parent('article').find('img')
        if img:
            src = img['src']
            kb = {"inline_keyboard":[[{"text":"عرض على MakerWorld","url":href}]]}
            tg_photo(src, f"🛠️ [MakerWorld • New]\n{title}", kb)
        else:
            tg_text(f"🛠️ [MakerWorld • New]\n{title}\n{href}")

def maker_trending_scrape():
    url = "https://makerworld.com/"
    resp = requests.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    # افتراض وجود ويدجيت للمقالات الرائجة
    items = soup.select('section.popular-posts li a')[:5]
    for a in items:
        href = a['href']
        mid  = href
        if mid in sent_maker_trending: continue
        sent_maker_trending.add(mid)
        title = a.text.strip()
        tg_text(f"⚡ [MakerWorld • Trending]\n{title}\n{href}")

# ───── 5. /search لجلب أفضل 10 من كل موقع ─────
def thingiverse_search(q):
    scraper = cloudscraper.create_scraper()
    url = f"https://www.thingiverse.com/search?q={quote(q)}&type=things"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for c in soup.select('.ThingCard')[:10]:
        a = c.select_one('.ThingCard__title a')
        title = a.text.strip()
        link  = "https://www.thingiverse.com" + a['href']
        img   = c.select_one('img.ThingCard__img')
        src   = img.get('data-src') or img.get('src')
        kb = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(src, f"🌍 [Thingiverse]\n{title}", kb)

def printables_search(q):
    scraper = cloudscraper.create_scraper()
    url = f"https://www.printables.com/search?query={quote(q)}"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a[data-cy="model-card-link"]')[:10]:
        title = a.select_one(".card__title").text.strip()
        link  = "https://www.printables.com" + a['href']
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(img, f"🧡 [Printables]\n{title}", kb)

def cults_search(q):
    scraper = cloudscraper.create_scraper()
    url = f"https://cults3d.com/en/search?q={quote(q)}"
    resp = scraper.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('a.card-product__link')[:10]:
        title = a.select_one(".card-product__name").text.strip()
        link  = "https://cults3d.com" + a['href']
        img   = a.find("img")['src']
        kb = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
        tg_photo(img, f"💜 [Cults3D]\n{title}", kb)

def maker_search(q):
    url = f"https://makerworld.com/?s={quote(q)}"
    resp = requests.get(url, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select('article h2.entry-title a')[:10]:
        title = a.text.strip()
        link  = a['href']
        img = a.find_parent('article').find('img')
        if img:
            kb = {"inline_keyboard":[[{"text":"عرض","url":link}]]}
            tg_photo(img['src'], f"🛠️ [MakerWorld]\n{title}", kb)
        else:
            tg_text(f"🛠️ [MakerWorld]\n{title}\n{link}")

@app.route("/webhook", methods=["POST"])
def webhook():
    upd = request.get_json()
    if not upd or "message" not in upd: return "",200
    text = upd["message"].get("text","")
    if text.startswith("/search"):
        parts = text.split(" ",1)
        if len(parts)<2 or not parts[1].strip():
            tg_text("▪️ الاستخدام: `/search كلمة_بحث`")
        else:
            q = parts[1].strip()
            tg_text(f"🔎 بحث: «{q}» — جلب أفضل ١٠ تصميمات:")
            thingiverse_search(q)
            printables_search(q)
            cults_search(q)
            maker_search(q)
    return "",200

# ───── الوظيفة الدورية (Newest + Trending) ─────
def periodic_worker():
    while True:
        try:
            thingiverse_latest_scrape()
            thingiverse_trending_scrape()
            printables_latest_scrape()
            printables_trending_scrape()
            cults_latest_scrape()
            cults_trending_scrape()
            maker_latest_scrape()
            maker_trending_scrape()
        except Exception as e:
            tg_text(f"❌ Periodic Worker Error:\n{e}")
        time.sleep(180)  # كل 3 دقائق

# ───── بدء البوت ─────
if __name__ == "__main__":
    Thread(target=keep_alive, daemon=True).start()
    Thread(target=periodic_worker, daemon=True).start()
    # ضبط Webhook عبر BotFather إلى: https://<YOUR_DOMAIN>/webhook
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","10000")))