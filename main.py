import os
import re
import math
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Render Health Check Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# Telegram Bot Token
BOT_TOKEN = "8167308959:AAE_dgMyyY7RxGAGKrlWCTrmkW8IutCWN8o"

def count_srt_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    matches = re.findall(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', content)
    return len(matches)

# /start command handler
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot အလုပ်လုပ်နေပါပြီ ခင်ဗျာ။ စာဖိုင် (.srt သို့မဟုတ် .txt) ပို့ပေးနိုင်ပါပြီ။")

# Document (.srt / .txt) handler
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_name = doc.file_name or ""
    
    if not (file_name.endswith('.txt') or file_name.endswith('.srt')):
        await update.message.reply_text("❌ `.txt` သို့မဟုတ် `.srt` စာဖိုင်များကိုသာ ပို့ပေးပါ ခင်ဗျာ။")
        return

    status_msg = await update.message.reply_text("📖 စာဖိုင်ထဲက စာကြောင်းရေကို သေချာ ရေတွက်နေပါသည်...")
    
    tg_file = await doc.get_file()
    download_path = f"temp_{doc.file_unique_id}_{file_name}"
    await tg_file.download_to_drive(download_path)

    try:
        if file_name.endswith('.srt'):
            total_lines = count_srt_blocks(download_path)
        else:
            with open(download_path, 'r', encoding='utf-8', errors='ignore') as f:
                total_lines = len([line for line in f.readlines() if line.strip()])

        reply_text = (
            f"📄 **FILENAME:** `{file_name}`\n"
            f"📊 **TOTAL LINES:** `{total_lines}` lines\n\n"
            f"💡 **လူဘယ်နှစ်ယောက် ခွဲချင်တာလဲ?**\n"
            f"ဒီစာကို Reply ပြန်ပြီး လူဦးရေ ဂဏန်း (ဥပမာ - `5`) လို့ ရိုက်ထည့်ပေးပါ။"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်ပွားပါသည်: {str(e)}")

    finally:
        if os.path.exists(download_path):
            os.remove(download_path)

# Reply Text (Split Calculator) handler
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message:
        return

    replied_text = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    if "TOTAL LINES:" not in replied_text:
        return

    num_text = msg.text.strip()
    if not num_text.isdigit():
        await msg.reply_text("❌ ကျေးဇူးပြု၍ လူဦးရေ ဂဏန်းသန့်သန့် (ဥပမာ- 2, 3, 5) သာ ရိုက်ထည့်ပေးပါ ခင်ဗျာ။")
        return

    num_people = int(num_text)
    if num_people <= 0:
        await msg.reply_text("❌ လူဦးရေသည် 1 ယောက်ထက် ပိုရပါမည်။")
        return

    file_name_match = re.search(r"FILENAME:\s*`?([^`\n]+)`?", replied_text)
    file_name = file_name_match.group(1).strip() if file_name_match else "Subtitle File"

    match = re.search(r"TOTAL LINES:\s*`?(\d+)`?", replied_text)
    if not match:
        await msg.reply_text("❌ စာကြောင်းရေ တွက်ချက်ရာတွင် အမှားအယွင်းရှိနေပါသည်။")
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

    await msg.reply_text(result_msg, parse_mode="Markdown")

def main():
    # Flask Health Check ကို Background Thread ဖြင့် run ခြင်း
    t = Thread(target=run_web, daemon=True)
    t.start()

    # python-telegram-bot Application စတင်ခြင်း
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_reply))

    print(">>> BOT STARTED SUCCESSFULLY VIA HTTPS POLLING <<<", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
