import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import time

# إعداد البوت
BOT_TOKEN = 'PASTE_YOUR_TOKEN_HERE'
CHAT_ID = 'PASTE_YOUR_CHAT_ID_HERE'
bot = Bot(token=BOT_TOKEN)

# روابط RSS
feeds = {
    "Thingiverse": "https://www.thingiverse.com/rss/instances",
    "Printables": "https://rss.stephenslab.top/feed?url=https://www.printables.com/model?ordering=newest"
}

# تجنب التكرار
sent_ids = set()

def fetch_makerworld():
    url = 'https://makerworld.com/en/models?sort=recent'
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    items = []
    for el in soup.select("a.model-card"):
        title = el.select_one(".title").get_text(strip=True) if el.select_one(".title") else "New Model"
        link = "https://makerworld.com" + el['href']
        item_id = link
        items.append({"id": item_id, "title": title, "link": link})
    return items

def fetch_rss(name, url):
    parsed = feedparser.parse(url)
    items = []
    for entry in parsed.entries:
        entry_id = entry.get("id", entry.get("link"))
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        items.append({"id": entry_id, "title": title, "link": link})
    return items

def main_loop():
    while True:
        results = []

        for name, url in feeds.items():
            try:
                results.extend(fetch_rss(name, url))
            except Exception as e:
                print(f"Error fetching from {name}: {e}")

        try:
            results.extend(fetch_makerworld())
        except Exception as e:
            print(f"Error fetching from MakerWorld: {e}")

        for item in results:
            if item['id'] not in sent_ids:
                sent_ids.add(item['id'])
                msg = f"{item['title']}\n{item['link']}"
                try:
                    bot.send_message(chat_id=CHAT_ID, text=msg)
                except Exception as e:
                    print(f"Telegram error: {e}")
        
        time.sleep(300)

if __name__ == "__main__":
    main_loop()