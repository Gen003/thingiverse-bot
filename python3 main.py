import requests
import time
import os
import telegram
from flask import Flask

# إعداد التوكن ومعرف القناة
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

# تخزين آخر معرف منشور
last_id = None

def fetch_latest():
    global last_id
    url = "https://www.thingiverse.com/search/page:1/type:things"
    response = requests.get("https://makerworld.com/api/search/models?query=&sort=latest&limit=1")
    
    try:
        data = response.json()
        item = data['items'][0]
        thing_id = item['id']

        if thing_id != last_id:
            title = item['name']
            link = f"https://makerworld.com/en/models/{thing_id}"
            image_url = item['thumbnail']['url']
            message = f"🆕 فكرة جديدة:\n\n{title}\n\n🔗 {link}"

            # تحميل الصورة مؤقتاً ثم إرسالها
            image_data = requests.get(image_url).content
            with open("temp.jpg", "wb") as f:
                f.write(image_data)
            
            with open("temp.jpg", "rb") as f:
                bot.send_photo(chat_id=CHAT_ID, photo=f, caption=message)

            last_id = thing_id
    except Exception as e:
        print("❌ Error:", e)

@app.route('/')
def home():
    return "Bot is alive!"

def run_bot():
    while True:
        fetch_latest()
        time.sleep(300)  # كل 5 دقائق

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)