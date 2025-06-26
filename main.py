import telegram
import requests
from bs4 import BeautifulSoup
import asyncio
import os
import sys

# --- الإعدادات وقراءة المتغيرات ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

if not BOT_TOKEN or not CHANNEL_ID:
    print("[خطأ فادح] لم يتم العثور على متغيرات البيئة. يرجى إضافتها في Render.")
    sys.exit(1)

SENT_LINKS_FILE = 'sent_links.txt'
bot = telegram.Bot(token=BOT_TOKEN)

# --- دوال مساعدة ---
def load_sent_links():
    if not os.path.exists(SENT_LINKS_FILE):
        return set()
    with open(SENT_LINKS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_sent_link(link):
    with open(SENT_LINKS_FILE, 'a', encoding='utf-8') as f:
        f.write(link + '\n')

# --- دوال غير متزامنة (لاحظ استخدام async/await) ---
async def send_to_telegram(title, link, image_url):
    """إرسال بيانات التصميم إلى قناة التليجرام بشكل غير متزامن"""
    try:
        message = f"<b>تصميم جديد تم رصده!</b>\n\n" \
                  f"<b>الاسم:</b> {title}\n" \
                  f"<b>المصدر:</b> {link.split('/')[2]}\n" \
                  f"<b>الرابط:</b> <a href='{link}'>اضغط هنا للتحميل</a>"

        # هنا التعديل الجوهري: استخدام await لإرسال الصورة
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=message,
            parse_mode=telegram.ParseMode.HTML
        )
        print(f"تم إرسال: {title}")
        return True
    except Exception as e:
        print(f"حدث خطأ أثناء إرسال التصميم: {e}")
        return False

# --- دوال فحص المواقع (تبقى كما هي في المنطق، ولكنها الآن جزء من نظام async) ---
async def check_printables(sent_links):
    print("\n[INFO] جار فحص Printables...")
    try:
        # ملاحظة: requests مكتبة متزامنة، يمكن استخدامها داخل الكود غير المتزامن
        # لكن في التطبيقات المعقدة جدًا يتم استبدالها بمكتبة مثل aiohttp
        url = 'https://www.printables.com/en/new'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        new_models = soup.find_all('div', class_='print-card', limit=5)
        for model in new_models:
            link_tag = model.find('a', class_='link')
            if not link_tag: continue
            relative_link = link_tag['href']
            full_link = f"https://www.printables.com{relative_link.split('?')[0]}"
            if full_link not in sent_links:
                title = link_tag.text.strip()
                img_tag = model.find('img')
                image_url = img_tag.get('src') if img_tag else None
                if image_url and title and await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(3)
    except Exception as e:
        print(f"[ERROR] فشل فحص Printables: {e}")

# (يمكن تطبيق نفس نمط asyncio.to_thread على بقية الدوال، لكن requests غالبًا ما تعمل بدون مشاكل)
# دوال Thingiverse و MakerWorld تبقى كما هي للتسهيل حاليًا

async def main():
    """الدالة الرئيسية غير المتزامنة التي تدير كل شيء"""
    print("--- مرصد المجسمات الرقمية يعمل الآن (النظام غير المتزامن) ---")
    
    try:
        # استخدام await لإرسال رسالة بدء التشغيل
        await bot.send_message(chat_id=CHANNEL_ID, text="🛰️ وحدة 'مرصد المجسمات' بدأت العمل الآن. حالة الاتصال: سليمة. جاري بدء الفحص الدوري...")
        print("[INFO] تم إرسال رسالة بدء التشغيل إلى تليجرام.")
    except Exception as e:
        print(f"[ERROR] فشل إرسال رسالة بدء التشغيل: {e}")

    sent_links = load_sent_links()
    print(f"[INFO] تم تحميل {len(sent_links)} رابط مرسل سابقاً.")

    while True:
        # هنا يمكنك استدعاء دوال الفحص
        await check_printables(sent_links)
        # await check_thingiverse(sent_links)  # يمكنك تفعيلها لاحقاً
        # await check_makerworld(sent_links) # يمكنك تفعيلها لاحقاً
        
        wait_time = 3600
        print(f"\n... اكتمل الفحص الدوري، في وضع الاستعداد لمدة {int(wait_time / 60)} دقيقة ...")
        # استخدام asyncio.sleep بدلاً من time.sleep
        await asyncio.sleep(wait_time)


if __name__ == '__main__':
    try:
        # تشغيل الدالة الرئيسية غير المتزامنة
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] تم إيقاف المرصد يدويًا.")
