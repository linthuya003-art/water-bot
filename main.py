import os
import sys
import logging
import traceback
import asyncio
from datetime import date, datetime
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────
#  Environment & Logging Setup
# ─────────────────────────────────────────────────────────────────────
load_dotenv()

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "gift_hub.log")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("gift_hub")

# ─────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN မရှိပါ။ .env file ထဲမှာ ထည့်ပါ။")
    sys.exit(1)

ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

KOYEB_PORT = int(os.environ.get("PORT", "8080"))
KOYEB_DOMAIN = os.environ.get("KOYEB_APP_URL", "").rstrip("/")
WEBHOOK_URL = f"{KOYEB_DOMAIN}/webhook" if KOYEB_DOMAIN else None

USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "false").lower() == "true"

logger.info("Bot configuration loaded")
logger.info("Bot Token: %s", "✓" if BOT_TOKEN else "✗")
logger.info("Admin IDs: %s", ADMIN_IDS if ADMIN_IDS else "Default admins only")
logger.info("Mode: %s", "Webhook" if USE_WEBHOOK else "Polling")

# ─────────────────────────────────────────────────────────────────────
#  Import Bot Components
# ─────────────────────────────────────────────────────────────────────
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from parser import parse_entry, parse_batch, format_reply, format_reply_summary
from database import (
    is_admin,
    add_admin,
    remove_admin,
    get_all_admins,
    delete_entry,
    get_entries_by_date,
    insert_entry,
    insert_batch_entries,
)
from report import format_daily_report_text, format_monthly_report_text, generate_excel


# ─────────────────────────────────────────────────────────────────────
#  Helper Functions
# ─────────────────────────────────────────────────────────────────────


def check_admin(user_id: int) -> bool:
    """
    Admin ဟုတ်/မဟုတ် စစ် — environment variable နဲ့ database ကိုပါ စစ်
    """
    if user_id in ADMIN_IDS:
        return True
    if is_admin(user_id):
        return True
    return False


async def send_reply(update: Update, text: str, reply_to: bool = True):
    """
    Message reply ပို့
    """
    reply_to_message_id = update.effective_message.message_id if reply_to else None
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_to_message_id=reply_to_message_id,
    )


async def send_document(update: Update, file_bytes: bytes, filename: str):
    """
    Document (Excel) ပို့
    """
    from io import BytesIO
    await update.message.reply_document(
        document=BytesIO(file_bytes),
        filename=filename,
    )


# ─────────────────────────────────────────────────────────────────────
#  Command Handlers — User Commands
# ─────────────────────────────────────────────────────────────────────


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — Bot စတင် အသုံးပြုပုံ ပြ
    """
    help_text = (
        "<b>🎁 Gift Hub — စာရင်းကိုင် Bot</b>\n\n"
        "ရေဘူး စာရင်း Bot ကို ကြိုဆိုပါသည်!\n\n"
        "<b>📝 စာရင်းထည့်နည်း:</b>\n"
        "Group ထဲမှာ format အတိုင်း ရိုက်ပါ:\n"
        "<code>နာမည် ဂဏန်း(ငွေ)</code>\n\n"
        "ဥပမာ:\n"
        "<code>ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)</code>\n"
        "<code>ကိုအသေး 30(1100)</code>\n\n"
        "<b>📋 Report Commands:</b>\n"
        "/today — ဒီနေ့ စာရင်း\n"
        "/month — ဒီလ စာရင်း\n"
        "/export — ဒီနေ့ Excel export\n\n"
        "<b>⚙️ Admin Commands:</b>\n"
        "/admin — Admin panel\n"
        "/addadmin — Admin ထည့်\n"
        "/removeadmin — Admin ဖျက်\n"
        "/delete — Entry ဖျက်\n"
        "/list — နေ့စဉ် စာရင်း list"
    )
    await send_reply(update, help_text, reply_to=False)

း
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help — အသုံးပြုနည်း ပြ
    """
    await start_command(update, context)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /today — ဒီနေ့ စာရင်း report
    """
    report_text = format_daily_report_text()
    await send_reply(update, report_text)


async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /month — ဒီလ စာရင်း report
    """
    now = datetime.now()
    report_text = format_monthly_report_text(now.year, now.month)
    await send_reply(update, report_text)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /export — ဒီနေ့ စာရင်း Excel export
    """
    excel_bytes = generate_excel(target_date=date.today())
    filename = f"gift_hub_{date.today().strftime('%Y%m%d')}.xlsx"
    await send_document(update, excel_bytes, filename)
    await send_reply(update, f"📊 {filename} Excel export ပြီးပါပြီ!")


# ─────────────────────────────────────────────────────────────────────
#  Command Handlers — Admin Commands
# ─────────────────────────────────────────────────────────────────────


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin — Admin panel ပြ
    """
    user_id = update.effective_user.id

    if not check_admin(user_id):
        await send_reply(update, "⛔ Admin command သုံးခွင့် မရှိပါ။")
        return

    admins = get_all_admins()

    text = "<b>⚙️ Admin Panel</b>\n\n"

    text += f"<b>Current Admins ({len(admins) + len(ADMIN_IDS)}):</b>\n"

    # Environment admins
    for aid in ADMIN_IDS:
        text += f"  🔒 {aid} (ENV)\n"

    # Database admins
    for a in admins:
        text += f"  👤 {a['telegram_id']} - {a['name']} ({a['added_at']})\n"

    text += "\n<b>Admin Commands:</b>\n"
    text += "/addadmin &lt;telegram_id&gt; &lt;name&gt;\n"
    text += "/removeadmin &lt;telegram_id&gt;\n"
    text += "/delete &lt;entry_id&gt;\n"
    text += "/list &lt;YYYY-MM-DD&gt;"

    await send_reply(update, text)


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /addadmin — Admin ထည့်
    """
    user_id = update.effective_user.id

    if not check_admin(user_id):
        await send_reply(update, "⛔ Admin command သုံးခွင့် မရှိပါ။")
        return

    if len(context.args) < 2:
        await send_reply(update, "⚠️ Format: /addadmin &lt;telegram_id&gt; &lt;name&gt;")
        return

    new_admin_id = int(context.args[0])
    new_admin_name = " ".join(context.args[1:])

    if add_admin(new_admin_id, new_admin_name):
        await send_reply(update, f"✅ Admin ထည့်ပြီး: {new_admin_name} ({new_admin_id})")
    else:
        await send_reply(update, "❌ Admin ထည့်မရပါ။")


async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /removeadmin — Admin ဖျက်
    """
    user_id = update.effective_user.id

    if not check_admin(user_id):
        await send_reply(update, "⛔ Admin command သုံးခွင့် မရှိပါ။")
        return

    if not context.args:
        await send_reply(update, "⚠️ Format: /removeadmin &lt;telegram_id&gt;")
        return

    remove_id = int(context.args[0])

    if remove_admin(remove_id):
        await send_reply(update, f"✅ Admin ဖျက်ပြီး: {remove_id}")
    else:
        await send_reply(update, "❌ Admin ဖျက်မရပါ။")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /delete — Entry ဖျက် (Admin only)
    """
    user_id = update.effective_user.id

    if not check_admin(user_id):
        await send_reply(update, "⛔ Admin command သုံးခွင့် မရှိပါ။")
        return

    if not context.args:
        await send_reply(update, "⚠️ Format: /delete &lt;entry_id&gt;\n\n"
                           "Entry ID ကို /list command နဲ့ ရယူနိုင်ပါသည်။")
        return

    try:
        entry_id = int(context.args[0])
    except ValueError:
        await send_reply(update, "⚠️ Entry ID ဂဏန်း ထည့်ပါ။")
        return

    if delete_entry(entry_id):
        await send_reply(update, f"✅ Entry #{entry_id} ဖျက်ပြီးပါပြီ!")
    else:
        await send_reply(update, f"❌ Entry #{entry_id} ဖျက်မရပါ။")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /list — နေ့တစ်ရက်ရဲ့ entries list ပြ (Admin)
    """
    user_id = update.effective_user.id

    if not check_admin(user_id):
        await send_reply(update, "⛔ Admin command သုံးခွင့် မရှိပါ။")
        return

    if context.args:
        try:
            target_date = date.fromisoformat(context.args[0])
        except ValueError:
            await send_reply(update, "⚠️ Date format: /list &lt;YYYY-MM-DD&gt;")
            return
    else:
        target_date = date.today()

    entries = get_entries_by_date(target_date)

    if not entries:
        await send_reply(update, f"📋 {target_date.strftime('%Y-%m-%d')}: စာရင်း မရှိ")
        return

    text = f"📋 <b>{target_date.strftime('%Y-%m-%d')} Entries ({len(entries)})</b>\n\n"

    for i, entry in enumerate(entries, 1):
        text += f"{i}. ID #{entry['id']} | {entry['customer_name']} | "
        text += f"{entry['bottles']} ဘူး | {entry['money']:,} Ks | "
        text += f"{entry['tier']} | {entry['entry_time'][:19]}\n"

    text += "\n💡 ဖျက်ချင်ရင်: /delete &lt;ID&gt;"

    await send_reply(update, text)


# ─────────────────────────────────────────────────────────────────────
#  Message Handler — Auto Parse Group Messages
# ─────────────────────────────────────────────────────────────────────


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Group ထဲက message တွေကို auto parse လုပ်
    """
    text = update.message.text

    if not text:
        return

    text = text.strip()

    # Empty or whitespace only
    if not text:
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.full_name or "Unknown"
    chat_type = update.effective_chat.type

    logger.info(
        "Message received: user=%s (%d) | chat=%s | text=%s",
        user_name, user_id, chat_type, text[:100]
    )

    # Single line message — parse one entry
    if "\n" not in text:
        entry = parse_entry(text)

        if entry:
            # Database ထဲ ထည့်
            try:
                row_id = insert_entry_to_db(user_id, user_name, entry)
                reply = format_reply(entry, user_name)
                await send_reply(update, reply)
            except Exception as e:
                logger.error("Insert failed: %s", e)
                await send_reply(update, "❌ စာရင်းထည့်မရပါ။ ပြန်ကြိုးပါ။")
        else:
            # Parse မရရင် error ပြ
            await send_reply(
                update,
                "⚠️ စာရင်း format မှားနေပါတယ်!\n\n"
                "Format: <b>နာမည် ဂဏန်း(ငွေ)</b>\n\n"
                "ဥပမာ:\n"
                "<code>ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)</code>\n"
                "<code>ကိုအသေး 30(1100)</code>\n\n"
                "Commands: /today, /month, /export, /admin"
            )
    else:
        # Multi-line message — batch parse
        entries = parse_batch(text)

        if entries:
            try:
                ids = insert_batch_to_db(user_id, user_name, entries)
                reply = format_reply_summary(entries, user_name)
                await send_reply(update, reply)
            except Exception as e:
                logger.error("Batch insert failed: %s", e)
                await send_reply(update, "❌ စာရင်း batch ထည့်မရပါ။ ပြန်ကြိုးပါ။")
        else:
            await send_reply(
                update,
                "⚠️ Batch စာရင်း parse မရပါ။ Format ကို ပြန်စစ်ပါ။\n\n"
                "Format: နာမည် ဂဏန်း(ငွေ)\n"
                "Example: ရေပေါ်ဘုန်းကြီးကျောင်း 13(1000)"
            )


# ─────────────────────────────────────────────────────────────────────
#  Database Helper Wrappers (with logging)
# ─────────────────────────────────────────────────────────────────────


def insert_entry_to_db(user_id: int, user_name: str, entry: dict) -> int:
    """
    Entry database ထဲ ထည့် (error handling wrapper)
    """
    try:
        row_id = insert_entry(user_id, user_name, entry)
        logger.info("Entry inserted: id=%d customer=%s", row_id, entry["name"])
        return row_id
    except Exception as e:
        logger.error("DB insert failed: %s — %s", e, traceback.format_exc())
        raise


def insert_batch_to_db(user_id: int, user_name: str, entries: list[dict]) -> list[int]:
    """
    Batch entries database ထဲ ထည့်
    """
    try:
        ids = insert_batch_entries(user_id, user_name, entries)
        logger.info("Batch inserted: %d entries", len(ids))
        return ids
    except Exception as e:
        logger.error("DB batch insert failed: %s — %s", e, traceback.format_exc())
        raise


# ─────────────────────────────────────────────────────────────────────
#  Error Handler
# ─────────────────────────────────────────────────────────────────────


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Global error handler
    """
    logger.error(
        "Exception while handling an update:\n%s",
        traceback.format_exc()
    )

    # Context အကြောင်း ရ
    if context.error:
        logger.error("Context error: %s", context.error)

    # User ကို error message ပို့ (အများကြီး spam မလုပ်)
    if update and update.effective_message:
        try:
            await update.message.reply_text(
                "⚠️ Bot error ဖြစ်နေပါတယ်။ နည်းနည်း စောင့်ပါ။"
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────
#  Bot Initialization
# ─────────────────────────────────────────────────────────────────────


def build_application() -> Application:
    """
    Application build — handlers register
    """
    # Application build
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Bot Commands (BotFather ကိုလည်း ထည့်ပေးရန်) ──
    commands = [
        BotCommand("start", "Bot စတင်"),
        BotCommand("help", "အသုံးပြုနည်း"),
        BotCommand("today", "ဒီနေ့ စာရင်း"),
        BotCommand("month", "ဒီလ စာရင်း"),
        BotCommand("export", "Excel export"),
        BotCommand("admin", "Admin panel"),
        BotCommand("addadmin", "Admin ထည့်"),
        BotCommand("removeadmin", "Admin ဖျက်"),
        BotCommand("delete", "Entry ဖျက်"),
        BotCommand("list", "Entries list"),
    ]

    async def set_commands_hook(application: Application):
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands set")

    app.post_init = set_commands_hook

    # ── Command Handlers ──
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("month", month_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addadmin", add_admin_command))
    app.add_handler(CommandHandler("removeadmin", remove_admin_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("list", list_command))

    # ── Message Handler — Group messages auto parse ──
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_message,
        )
    )

    # ── Private messages ထဲက စာရင်းလည်း parse လုပ် ──
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_message,
        )
    )

    # ── Error Handler ──
    app.add_error_handler(error_handler)

    return app


def run_polling(application: Application):
    """
    Polling mode မှာ run
    """
    logger.info("Bot starting in POLLING mode")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


async def run_webhook(application: Application):
    """
    Webhook mode မှာ run (Koyeb deploy အတွက်)
    """
    if not WEBHOOK_URL:
        logger.error("KOYEB_APP_URL environment variable မရှိပါ!")
        sys.exit(1)

    logger.info("Bot starting in WEBHOOK mode: %s", WEBHOOK_URL)
    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
    )

    await application.updater.start_webhook(
        listen="0.0.0.0",
        port=KOYEB_PORT,
        url_path=BOT_TOKEN,
        webhook_url=WEBHOOK_URL,
    )

    logger.info("Webhook server running on port %d", KOYEB_PORT)
    await application.start()

    import asyncio
    await asyncio.Event().wait()  # Forever run


# ─────────────────────────────────────────────────────────────────────
#  Main Entry Point
# ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🎁 Gift Hub Bot starting...")
    logger.info("=" * 60)

    # Initialize database
    import database
    database.init_db()

    # Build application
    application = build_application()

    # Run mode select
    if USE_WEBHOOK:
        logger.info("Webhook mode selected")
        asyncio = __import__("asyncio")
        asyncio.run(run_webhook(application))
    else:
        logger.info("Polling mode selected")
        run_polling(application)
