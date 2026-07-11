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


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


def main():
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
