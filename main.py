import os
import re
import math
import asyncio
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, idle
from pyrogram.types import Message

# Render Health Check Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# Telegram Credentials
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8167308959:AAE_dgMyyY7RxGAGKrlWCTrmkW8IutCWN8o"

# ipv6=False ထည့်သွင်းထားပြီး sleep_threshold တိုးထားသည်
app = Client(
    "line_calc_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    in_memory=True,
    ipv6=False,
    sleep_threshold=60
)

def count_srt_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    matches = re.findall(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', content)
    return len(matches)

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    print(f"[LOG] /start received from {message.from_user.id}", flush=True)
    await message.reply_text("👋 Bot အလုပ်လုပ်နေပါပြီ ခင်ဗျာ။ စာဖိုင် (.srt သို့မဟုတ် .txt) ပို့ပေးနိုင်ပါပြီ။")

@app.on_message(filters.document)
async def check_file_lines(client: Client, message: Message):
    print(f"[LOG] Document received: {message.document.file_name}", flush=True)
    doc = message.document
    if not (doc.file_name.endswith('.txt') or doc.file_name.endswith('.srt')):
        await message.reply_text("❌ `.txt` သို့မဟုတ် `.srt` စာဖိုင်များကိုသာ ပို့ပေးပါ ခင်ဗျာ။")
        return

    status_msg = await message.reply_text("📖 စာဖိုင်ထဲက စာကြောင်းရေကို သေချာ ရေတွက်နေပါသည်...")
    file_path = await message.download(file_name=doc.file_name)

    try:
        if doc.file_name.endswith('.srt'):
            total_lines = count_srt_blocks(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                total_lines = len([line for line in f.readlines() if line.strip()])

        reply_text = (
            f"📄 **FILENAME:** `{doc.file_name}`\n"
            f"📊 **TOTAL LINES:** `{total_lines}` lines\n\n"
            f"💡 **လူဘယ်နှစ်ယောက် ခွဲချင်တာလဲ?**\n"
            f"ဒီစာကို Reply ပြန်ပြီး လူဦးရေ ဂဏန်း (ဥပမာ - `5`) လို့ ရိုက်ထည့်ပေးပါ။"
        )
        await message.reply_text(reply_text)
        await status_msg.delete()

    except Exception as e:
        print(f"[ERROR in document handler]: {str(e)}", flush=True)
        await status_msg.edit_text(f"❌ Error ဖြစ်ပွားပါသည်: {str(e)}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.on_message(filters.reply & filters.text)
async def calculate_line_split(client: Client, message: Message):
    print(f"[LOG] Reply text received: {message.text}", flush=True)
    replied_msg = message.reply_to_message
    raw_text = replied_msg.text or replied_msg.caption or ""

    if "TOTAL LINES:" not in raw_text:
        return

    num_text = message.text.strip()
    if not num_text.isdigit():
        await message.reply_text("❌ ကျေးဇူးပြု၍ လူဦးရေ ဂဏန်းသန့်သန့် (ဥပမာ- 2, 3, 5) သာ ရိုက်ထည့်ပေးပါ ခင်ဗျာ။")
        return

    num_people = int(num_text)
    if num_people <= 0:
        await message.reply_text("❌ လူဦးရေသည် 1 ယောက်ထက် ပိုရပါမည်။")
        return

    file_name_match = re.search(r"FILENAME:\s*`?([^`\n]+)`?", raw_text)
    file_name = file_name_match.group(1).strip() if file_name_match else "Subtitle File"

    match = re.search(r"TOTAL LINES:\s*`?(\d+)`?", raw_text)
    if not match:
        await message.reply_text("❌ စာကြောင်းရေ တွက်ချက်ရာတွင် အမှားအယွင်းရှိနေပါသည်။")
        return

    total_lines = int(match.group(1))
    lines_per_person = math.ceil(total_lines / num_people)

    result_msg = (
        f"🎬 **{file_name}**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Total Lines:** {total_lines} ( ~{lines_per_person} lines / each )\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
    )

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    current_start = 1

    for i in range(1, num_people + 1):
        current_end = current_start + lines_per_person - 1
        
        if i == num_people or current_end > total_lines:
            current_end = total_lines

        label = f"({alphabet[(i - 1) % 26]})"
        result_msg += f"{label} {current_start} - {current_end} > \n"

        if current_end >= total_lines:
            break

        current_start = current_end + 1

    await message.reply_text(result_msg)

async def main():
    # Flask Server ကို Background Thread မှာ မောင်းနှင်ခြင်း
    t = Thread(target=run_web, daemon=True)
    t.start()

    # Bot ကို Reconnect Auto-retry စနစ်ဖြင့် Run ခြင်း
    while True:
        try:
            print(">>> CONNECTING TO TELEGRAM MTPROTO...", flush=True)
            await app.start()
            print(">>> BOT CONNECTED & RUNNING 24/7 <<<", flush=True)
            await idle()
            await app.stop()
            break
        except (asyncio.TimeoutError, TimeoutError, Exception) as err:
            print(f"[WARN] Connection dropped ({err}). Reconnecting in 5 seconds...", flush=True)
            try:
                await app.stop()
            except Exception:
                pass
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
