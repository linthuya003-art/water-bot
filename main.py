import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN
from parser import calculate_water
from database import create_table, save_record

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text

    result = calculate_water(text)

    if result["total_bottles"] == 0:
        return

    prices = result["prices"]

    reply = (
        "📋 စာရင်းချုပ်\n\n"
        f"💰 1000 = {prices[1000]} ဘူး = {prices[1000] * 1000:,} ကျပ်\n"
        f"💰 1100 = {prices[1100]} ဘူး = {prices[1100] * 1100:,} ကျပ်\n"
        f"💰 1300 = {prices[1300]} ဘူး = {prices[1300] * 1300:,} ကျပ်\n\n"
        "━━━━━━━━━━━━\n"
        f"🧴 ရေဘူးစုစုပေါင်း = {result['total_bottles']} ဘူး\n"
        f"💵 စုစုပေါင်းငွေ = {result['total_money']:,} ကျပ်\n"
        f"👥 ဖောက်သည် = {result['customers']} ဦး\n"
        "━━━━━━━━━━━━"
    )
save_record(
    update.message.from_user.first_name,
    result["total_bottles"],
    result["total_money"]
)
    await update.message.reply_text(reply)


def main():
    create_table()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("စာရင်းကိုင် Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()
