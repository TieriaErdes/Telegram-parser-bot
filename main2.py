"""
First, a few callback functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

GENDER, ADRESS = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и спрашивает у пользователя чего он бы хотел"""
    reply_keyboard = [["Да", "Нет"]]

    await update.message.reply_text(
        "Привет! Прости, что я так уродлив. Просто мой создатель овощ. \n"
        "Отправь /cancel Для завершения разговора \n\n"
        "Ты натурал?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Натурал или да?"
        ),
    )

    return GENDER

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Когда убедились что пользователь натурал"""
    """Хранит гендер и работаем дальше"""
    user = update.message.from_user
    logger.info("Gender of %s (id %s): %s", user.first_name, user.id, update.message.text)

    reply_keyboard = [[]]

    if update.message.text == 'Да':
        await update.message.reply_text(
            "Всё-всё, вижу что ты харош. Давай теперь работать (cкинь ссылку) \n"
            "Можешь отправить /skip, если не хочешь общаться со мной.",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, input_field_placeholder="Ссылку на базу"
            ),
        )
    else:
        await update.message.reply_text(
            "Иди нахер, пидорас \n",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    return ADRESS

async def adress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Хранит ссылку и пока что всё"""
    user = update.message.from_user
    str = update.message.text
    logger.info("Ccылка от %s: %s", user.first_name, str)
    await update.message.reply_text(
        f"Красавчик! Думал я уже начал работать? Ну получай обратно {str} \n"
    )

    return ConversationHandler.END


async def skip_adress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the photo and asks for a location."""
    user = update.message.from_user
    logger.info("User %s did not send a photo.", user.first_name)
    await update.message.reply_text(
        "I bet you look great! Now, send me your location please, or send /skip."
    )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Прощай, мой милый друг", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7460009035:AAFb_uzUkhiTQDp0mNtx68Ia6xVdPrRU9Hs").build()

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.Regex("^(Да|Нет)$"), gender)],
            ADRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, adress), CommandHandler("skip", skip_adress)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


