import os
import re
import math
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message

# Render Port Error မတက်အောင် Web Server သေးသေးလေး ဆောက်ခြင်း
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# Credentials
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8167308959:AAE_dgMyyY7RxGAGKrlWCTrmkW8IutCWN8o"

app = Client("line_calc_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 1. စာဖိုင်ပို့လိုက်ရင် စာကြောင်းရေ ဖတ်ပေးမည့် Handler
@app.on_message(filters.document)
async def check_file_lines(client: Client, message: Message):
    doc = message.document
    if not (doc.file_name.endswith('.txt') or doc.file_name.endswith('.srt')):
        await message.reply_text("❌ `.txt` သို့မဟုတ် `.srt` စာဖိုင်များကိုသာ ပို့ပေးပါ ခင်ဗျာ။")
        return

    status_msg = await message.reply_text("📖 စာဖိုင်ထဲက စာကြောင်းရေကို ရေတွက်နေပါသည်...")
    file_path = await message.download(file_name=doc.file_name)

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        total_lines = len(lines)

        reply_text = (
            f"📄 **ဖိုင်နာမည်:** `{doc.file_name}`\n"
            f"📊 **စုစုပေါင်း စာကြောင်းရေ:** `{total_lines}` lines\n\n"
            f"💡 **လူဘယ်နှစ်ယောက် ခွဲချင်တာလဲ?**\n"
            f"ဒီစာကို Reply ပြန်ပြီး လူဦးရေ ဂဏန်း (ဥပမာ - `5`) လို့ ရိုက်ထည့်ပေးပါ။"
        )
        await message.reply_text(reply_text)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်ပွားပါသည်: {str(e)}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# 2. ပြန်လာမယ့် Reply ကို တွက်ချက်ပေးမည့် Handler
@app.on_message(filters.reply & filters.text)
async def calculate_line_split(client: Client, message: Message):
    replied_msg = message.reply_to_message
    if not replied_msg.text or "စုစုပေါင်း စာကြောင်းရေ:" not in replied_msg.text:
        return

    num_text = message.text.strip()
    if not num_text.isdigit():
        await message.reply_text("❌ ကျေးဇူးပြု၍ လူဦးရေ ဂဏန်းသန့်သန့် (ဥပမာ- 2, 3, 5) သာ ရိုက်ထည့်ပေးပါ ခင်ဗျာ။")
        return

    num_people = int(num_text)
    if num_people <= 0:
        await message.reply_text("❌ လူဦးရေသည် 1 ယောက်ထက် ပိုရပါမည်။")
        return

    # Regex သုံး၍ စုစုပေါင်း စာကြောင်းရေ ဂဏန်းကို ရှာဖွေခွဲထုတ်ခြင်း
    match = re.search(r"စုစုပေါင်း စာကြောင်းရေ:\s*`?(\d+)`?", replied_msg.text)
    if not match:
        await message.reply_text("❌ စာကြောင်းရေ တွက်ချက်ရာတွင် အမှားအယွင်းရှိနေပါသည်။")
        return

    total_lines = int(match.group(1))

    lines_per_person = math.ceil(total_lines / num_people)

    result_msg = f"📊 **စုစုပေါင်း:** `{total_lines}` Lines\n"
    result_msg += f"👥 **လူဦးရေ:** `{num_people}` ယောက် (၁ ယောက်လျှင် ~ `{lines_per_person}` lines)\n\n"
    result_msg += "✂️ **Line ခွဲဝေမှု စာရင်း -**\n"
    result_msg += "───────────────\n"

    current_start = 1
    for i in range(1, num_people + 1):
        current_end = current_start + lines_per_person - 1
        
        if i == num_people or current_end > total_lines:
            current_end = total_lines

        result_msg += f"👤 **Person {i}:** Line `{current_start}` - `{current_end}`\n"

        if current_end >= total_lines:
            break

        current_start = current_end + 1

    await message.reply_text(result_msg)

if __name__ == "__main__":
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    
    app.run()
