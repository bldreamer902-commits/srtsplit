import html
import logging
import math
import os
import re
import tempfile
from pathlib import Path
from threading import Thread

from flask import Flask
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# -------------------- Configuration --------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 20 * 1024 * 1024))
MAX_PEOPLE = int(os.environ.get("MAX_PEOPLE", 100))
PORT = int(os.environ.get("PORT", "10000"))
DROP_PENDING_UPDATES = os.environ.get("DROP_PENDING_UPDATES", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("srtsplit")

# -------------------- Health-check web server --------------------
web_app = Flask(__name__)


@web_app.get("/")
def home():
    return "Bot is alive and running!", 200


@web_app.get("/health")
def health():
    return {"status": "ok"}, 200


def run_web_server():
    logger.info("Starting health server on 0.0.0.0:%s", PORT)
    # This server is only for the hosting platform health check.
    web_app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)


# -------------------- File helpers --------------------
SRT_TIMING_RE = re.compile(
    r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*"
    r"\d{2}:\d{2}:\d{2}[,.]\d{3}"
)


def count_srt_blocks(file_path: Path) -> int:
    """Count SRT subtitle blocks without loading the whole file into RAM."""
    count = 0
    with file_path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            if SRT_TIMING_RE.search(line):
                count += 1
    return count


def count_nonempty_lines(file_path: Path) -> int:
    with file_path.open("r", encoding="utf-8", errors="replace") as file:
        return sum(1 for line in file if line.strip())


def extract_filename(reply_text: str) -> str:
    match = re.search(r"FILENAME:\s*<code>(.*?)</code>", reply_text, re.IGNORECASE | re.DOTALL)
    if match:
        return html.unescape(match.group(1))
    return "Subtitle File"


def extract_total_lines(reply_text: str):
    match = re.search(r"TOTAL LINES:\s*<code>(\d+)</code>", reply_text, re.IGNORECASE)
    return int(match.group(1)) if match else None


# -------------------- Telegram handlers --------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        logger.info("/start received from user_id=%s", update.effective_user.id)
    await update.message.reply_text(
        "Bot အလုပ်လုပ်နေပါပြီ။ .srt သို့မဟုတ် .txt ဖိုင် ပို့ပေးနိုင်ပါပြီ။"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.document:
        return

    document = message.document
    original_name = document.file_name or "file.srt"
    file_name = Path(original_name).name
    lower_name = file_name.lower()
    logger.info("Document received: %s, size=%s", file_name, document.file_size)

    if not lower_name.endswith((".srt", ".txt")):
        await message.reply_text(".srt သို့မဟုတ် .txt ဖိုင်များကိုသာ ပို့ပေးပါ။")
        return

    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"ဖိုင်အရွယ်အစား ကြီးလွန်းပါတယ်။ {MAX_FILE_SIZE // (1024 * 1024)} MB အောက်သာ ပို့ပေးပါ။"
        )
        return

    status_message = await message.reply_text("ဖိုင်ကို download လုပ်ပြီး စာကြောင်းရေတွက်နေပါတယ်...")
    temp_path = None

    try:
        await message.chat.send_action(ChatAction.TYPING)
        telegram_file = await document.get_file()
        logger.info("Telegram file info received: %s", file_name)

        with tempfile.NamedTemporaryFile(prefix="srtsplit_", suffix=Path(file_name).suffix, delete=False) as temp:
            temp_path = Path(temp.name)

        await telegram_file.download_to_drive(custom_path=str(temp_path))
        actual_size = temp_path.stat().st_size
        logger.info("Download completed: %s bytes, path=%s", actual_size, temp_path)

        if actual_size > MAX_FILE_SIZE:
            raise ValueError("Downloaded file is larger than the configured limit")

        if lower_name.endswith(".srt"):
            total_lines = count_srt_blocks(temp_path)
        else:
            total_lines = count_nonempty_lines(temp_path)

        logger.info("Counting completed: file=%s total_lines=%s", file_name, total_lines)
        safe_name = html.escape(file_name)
        reply_text = (
            f"📄 <b>FILENAME:</b> <code>{safe_name}</code>\n"
            f"📊 <b>TOTAL LINES:</b> <code>{total_lines}</code> lines\n\n"
            "လူဘယ်နှစ်ယောက်ခွဲချင်ပါသလဲ?\n"
            "ဒီစာကို Reply ပြန်ပြီး ဂဏန်း (ဥပမာ - <code>5</code>) ရိုက်ထည့်ပါ။"
        )
        await status_message.edit_text(reply_text, parse_mode="HTML")
        logger.info("Reply sent successfully: file=%s", file_name)

    except Exception:
        logger.exception("Document processing failed: %s", file_name)
        try:
            await status_message.edit_text(
                "ဖိုင်ကို ပြင်ဆင်ရာမှာ အမှားဖြစ်သွားပါတယ်။ ဖိုင်သေးသေးတစ်ခုနဲ့ ထပ်စမ်းပေးပါ။"
            )
        except Exception:
            logger.exception("Could not edit status message")
    finally:
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.exception("Could not remove temporary file: %s", temp_path)


async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.reply_to_message or not message.text:
        return

    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if "TOTAL LINES:" not in replied_text:
        return

    number_text = message.text.strip()
    if not number_text.isdigit():
        await message.reply_text("လူဦးရေကို ဂဏန်းသန့်သန့်သာ ရိုက်ထည့်ပါ။ ဥပမာ - 2, 3, 5")
        return

    people = int(number_text)
    total_lines = extract_total_lines(replied_text)
    if people <= 0 or people > MAX_PEOPLE:
        await message.reply_text(f"လူဦးရေကို 1 မှ {MAX_PEOPLE} အတွင်း ထည့်ပေးပါ။")
        return
    if total_lines is None:
        await message.reply_text("စာကြောင်းရေကို ဖတ်မရပါ။ ဖိုင်ကို ပြန်ပို့ပြီး ထပ်စမ်းပါ။")
        return
    if total_lines <= 0:
        await message.reply_text("ဖိုင်ထဲမှာ subtitle စာကြောင်း မတွေ့ပါ။")
        return

    file_name = html.escape(extract_filename(replied_text))
    per_person = math.ceil(total_lines / people)
    result = [
        f"🎬 <b>{file_name}</b>",
        "━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Total Lines:</b> {total_lines} (~{per_person} lines each)",
        "━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    for index in range(people):
        start = index * per_person + 1
        end = min((index + 1) * per_person, total_lines)
        if start > total_lines:
            break
        label = alphabet[index] if index < len(alphabet) else str(index + 1)
        result.append(f"({label}) {start} - {end} &gt;")

    await message.reply_text("\n".join(result), parse_mode="HTML")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Telegram handler error: %r", context.error, exc_info=context.error)


async def post_init(application: Application) -> None:
    # Polling and webhook cannot be active together. Keep queued messages by default.
    logger.info("Removing any old Telegram webhook; drop_pending_updates=%s", DROP_PENDING_UPDATES)
    await application.bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    logger.info("Webhook cleared; polling is ready")


# -------------------- Startup --------------------
if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True, name="health-server").start()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter(overall_max_rate=30, overall_time_period=1))
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_reply))
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram polling")
    application.run_polling(
        drop_pending_updates=DROP_PENDING_UPDATES,
        bootstrap_retries=5,
    )
