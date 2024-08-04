#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to handle '(my_)chat_member' updates.
Greets new users & keeps track of which chats the bot is in.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import re
import html
import random
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple

from telegram import Chat, ChatMember, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Набор эмодзи
_members_emodzi_list = ['👮‍♂️', '👷‍♀️', '💂‍♀️', '🕵️‍♀️', '👩‍⚕️', '👨‍⚕️', '👩‍🌾',
                        '👩‍🍳', '👩‍🎓', '👩‍🎤', '🧑‍🎤', '👨‍🎤', '👩‍🏫', '🧑‍🏫',
                        '👩‍🏭', '👩‍💻', '👩‍💼', '👨‍💼', '👩‍🔧', '👩‍🔬', '👩‍🎨',
                        '🧑‍🔬', '👨‍🎨', '👩‍🚒', '👩‍✈️', '👩‍🚀', '👩‍⚖️', '👨‍⚖️',
                        '👰‍♀️', '🤵‍♀️', '🤵‍♂️', '👸', '🤴', '🥷', '🦸‍♀️', '🦸‍♂️',
                        '🦹‍♀️', '🤶', '🧙‍♀️', '🧝‍♀️', '🧝', '🧌', '🧛‍♀️', '🧛‍♂️',
                        '👼', '🤰', '🫃', '💁‍♀️', '💁‍♂️', '🙅‍♀️', '🙆‍♀️', '🙆', '🙋‍♀️',
                        '🙋‍♂️', '🧏‍♀️', '🤦‍♀️', '🤦', '🤷‍♀️', '🙎‍♀️', '🙍‍♀️', '🙍‍♂️',
                        '💇‍♀️', '💇‍♂️', '💆‍♀️', '💆‍♂️', '💅', '💃', '🕺', '🧑‍🦽', '🪢',
                        '🧶', '🧵', '🪡', '🧥', '🥼', '🦺', '👚', '👕', '👖', '🩲',
                        '🩳', '👔', '👗', '👙', '🩱', '👘', '🥻', '🩴', '🥿', '👠', '👡',
                        '👢', '👞', '👟', '🥾', '🧦', '🧤', '🧣', '🎩', '🧢']

DATABASE_PATH = 'database.db'


def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member

async def add_users_in_bd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    chat_id = update.effective_chat.id
    logger.info('Добавление участников чата "%s" в БД', update.effective_chat.title)
    chat_admins = await update.effective_chat.get_administrators()
    # Получаем список имен и фамилий
    admins_ids = [(admins.user.id) for admins in chat_admins]
    for admin_id in admins_ids:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (chat_id, admin_id, 0, None))
    conn.commit()
    conn.close()

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks the chats the bot is in."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            # This may not be really needed in practice because most clients will automatically
            # send a /start command after the user unblocks the bot, and start_private_chat()
            # will add the user to "user_ids".
            # We're including this here for the sake of the example.
            logger.info("%s разблокировал бота", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s заблокировал бота", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info('%s добавил бота в чат "%s"', cause_name, chat.title)
            # добавление чата в бд
            await add_users_in_bd(update, context)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info('%s исключил бота из чата "%s"', cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    elif not was_member and is_member:
        logger.info("%s добавил бота в канал %s", cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).add(chat.id)
    elif was_member and not is_member:
        logger.info("%s исключил бота из канала %s", cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).discard(chat.id)





async def call(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает список участников чата"""
    logger.info("%s вызвал список участников в чате %s", update.effective_user.full_name, update.effective_chat.title)

    chat_id = update.effective_chat.id
    members_count = await context.bot.get_chat_member_count(chat_id)
    print(f"Чат {update.effective_chat.title} имеет {members_count} участников.")

    #for member in context.bot.iter_chat_members(chat_id):
    #    print(member)

    chat_admins = await update.effective_chat.get_administrators()


    # Создаем список ID пользователей
    admin_ids = [(admins.user.id) for admins in chat_admins]

    print(admin_ids)

    admins_links = ""
    for admin_id in admin_ids:
        admins_links += (f' <a href="tg://user?id={admin_id}">{_members_emodzi_list[admin_id % 100]}</a>')

    await update.effective_chat.send_message(admins_links, parse_mode='HTML')

    # мой id
    #await update.message.reply_text(f" {await update.effective_chat.get_member(975108088)}")

    #await update.message.reply_text(f'Список участников чата "{update.effective_chat.title}".')




async def show_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('%s вызвал список админов в чате "%s"', update.effective_user.full_name, update.effective_chat.title)

    chat_admins = await update.effective_chat.get_administrators()
    # Получаем список имен и фамилий
    admins_custom_titles = [(admins.custom_title) for admins in chat_admins]
    admins_ids = [(admins.user.id) for admins in chat_admins]
    # Выводим результат
    #print(names_and_surnames)

    user_links = ""
    for admin_id, admin_custom_title in zip(admins_ids, admins_custom_titles):
        if admin_custom_title != None:
            user_links += (f'<a href="tg://user?id={admin_id}">{admin_custom_title + _members_emodzi_list[admin_id % 100]}</a>\n')
        else:
            user_links += (
                f'<a href="tg://user?id={admin_id}">{_members_emodzi_list[admin_id % 100]}</a>\n')

    await update.effective_chat.send_message(user_links, parse_mode='HTML')

async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows which chats the bot is in"""

    print(f"{context.bot_data}")

    user_ids = ", ".join(str(uid) for uid in context.bot_data.setdefault("user_ids", set()))
    group_ids = ", ".join(str(gid) for gid in context.bot_data.setdefault("group_ids", set()))
    channel_ids = ", ".join(str(cid) for cid in context.bot_data.setdefault("channel_ids", set()))
    text = (
        f"@{context.bot.username} в настоящее время находится в диалоге с пользователями {user_ids}. \n"
        f" Более того, он является членом групп с ID {group_ids} \n"
        f"и администратором в каналах с ID {channel_ids}."
    )
    await update.effective_message.reply_text(text)


# Функция вывода списка команд
async def help(update: Update, bot: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('%s вызвал список команд бота в чате "%s"', update.effective_user.full_name, update.effective_chat.title)
    await update.message.reply_text(f"Список команд: \n"
                                    f"/{call.__name__} \n"
                                    f"/{help.__name__} \n"
                                    f"/{show_chats.__name__} \n"
                                    f"/{show_admins.__name__} \n"
                                    "калл \n"
                                    "помощь \n"
                                    "help \n"
                                    "памагити \n"
                                    "список \n"
                                    "список участников \n"
                                    "чаты с ботом \n"
                                    "снег \n"
                                    "моя стата снега \n"
                                    "стата снега \n"
                                    "пинг"
                                    )

async def unknown(update: Update, bot: ContextTypes.DEFAULT_TYPE) -> None:
    #logger.info('%s вызвал неизвестную команду команд бота в чате "%s"', update.effective_user.full_name, update.effective_chat.title)
    #await update.message.reply_text("Данная команда мне неизвестна. Попробуйте /help для списка доступных команд.")
    i = 1


async def greet_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new users in chats and announces when someone leaves"""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    if not was_member and is_member:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        existing_spoons = c.fetchone()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (update.effective_chat.id, update.effective_user.id, 0, None))
        conn.commit()
        conn.close()
        await update.effective_chat.send_message(
            f"{member_name} добавлен {cause_name}. Добро пожаловать!",
            parse_mode=ParseMode.HTML,
        )
    elif was_member and not is_member:
        await update.effective_chat.send_message(
            f"{member_name} больше не с нами. Больщое спасибо, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


async def start_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets the user and records that they started a chat with the bot if it's a private chat.
    Since no `my_chat_member` update is issued when a user starts a private chat with the bot
    for the first time, we have to track it explicitly here.
    """
    user_name = update.effective_user.full_name
    chat = update.effective_chat
    if chat.type != Chat.PRIVATE or chat.id in context.bot_data.get("user_ids", set()):
        return

    logger.info("%s started a private chat with the bot", user_name)
    context.bot_data.setdefault("user_ids", set()).add(chat.id)

    await update.effective_message.reply_text(
        f"Добро пожаловать {user_name}. Используй команду /show_chats чтобы увидеть в каких чатах я есть."
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Понг")


#игровой код
#игровой код

async def get_random_snow_spoons():
    return random.randint(1, 10)

# Константы для определения интервала блокировки
INTERVAL_SECONDS = 6 * 60 * 60  # 6 часов в секундах

# Переменные для отслеживания времени последнего вызова
last_call_times = {}

# Функция для обработки команды "снег"
async def snow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Проверка времени до следующего вызова
    now = datetime.utcnow()
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        last_call_time_str = c.execute("SELECT last_snow_command_time FROM users WHERE chat_id = ? AND user_id = ?",
                                       (chat_id, user_id)).fetchone()[0]
    except TypeError:  # Или более общий вариант: except Exception as e:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (chat_id, user_id, 0, None))
        conn.commit()
        last_call_time_str = c.execute("SELECT last_snow_command_time FROM users WHERE chat_id = ? AND user_id = ?",
                                       (chat_id, user_id)).fetchone()[0]

    if last_call_time_str is not None:
        # Удаление лишних символов после даты и времени
        last_call_time_str_clean = re.sub(r'\.\d+$', '', last_call_time_str)
        # Преобразование строки в объект datetime.datetime
        last_call_time = datetime.strptime(last_call_time_str_clean, '%Y-%m-%d %H:%M:%S')
        if now - last_call_time < timedelta(seconds=INTERVAL_SECONDS):
            # Если время еще не прошло, прервать выполнение функции
            # Вывод сообщения о времени ожидания
            remaining_time = timedelta(seconds=INTERVAL_SECONDS) - (now - last_call_time)
            if remaining_time > timedelta(0):
                remaining_hours = int(remaining_time // timedelta(hours=1))
                remaining_minutes = int((remaining_time - timedelta(hours=remaining_hours)).total_seconds() // 60)
                remaining_seconds = int((remaining_time - timedelta(minutes=remaining_minutes)).total_seconds() % 60)
                remaining_time_string = f"Осталось {remaining_hours} час{'а' if remaining_hours == 1 else 'ов'}, " \
                                        f"{remaining_minutes} минут и {remaining_seconds} секунд."
                await context.bot.send_message(chat_id=update.effective_chat.id, text=remaining_time_string)
                conn.close()
            return

    # Обновление времени последнего вызова
    #last_call_times[user_id] = now

    # Обновление данных в базе
    c.execute("UPDATE users SET last_snow_command_time = ? WHERE chat_id = ? AND user_id = ?", (now, chat_id, user_id))
    conn.commit()

    spoon_count = await get_random_snow_spoons()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Вы съели {spoon_count} ложек снега!")

    # Проверка наличия данных и обновление
    c.execute("SELECT snow_spoons FROM users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    existing_spoons = c.fetchone()
    if existing_spoons is not None:
        new_spoons_count = int(existing_spoons[0]) + spoon_count
        c.execute("UPDATE users SET snow_spoons = ? WHERE chat_id = ? AND user_id = ?",
                  (new_spoons_count, chat_id, user_id))
        conn.commit()
    else:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (chat_id, user_id, spoon_count))
        conn.commit()
    conn.close()



# Создание базы данных и таблицы для хранения данных
def create_database():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER KEY, user_id INTEGER KEY, snow_spoons INTEGER, last_snow_command_time DATETIME)")
    conn.close()

create_database()


async def show_snow_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT snow_spoons FROM users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    stats = c.fetchone()
    conn.close()
    if stats is None:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Пока что вы ещё не дегустировали снег в этом чате.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"На данный момент Вы съели {stats[0]} ложек снега.")



async def allChat_snow_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT snow_spoons FROM users WHERE chat_id = ?", (chat_id,))
    total_spoons = c.fetchone()
    if total_spoons is None:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"К сожалению, в этом чате ещё никто не пробовал снег... Неужели все боятся, что им попадётся жёлтый?)")
    else:
        chat_admins = await update.effective_chat.get_administrators()
        # Создаем список ID пользователей
        admins_custom_titles = [(admins.custom_title) for admins in chat_admins]
        admins_ids = [(admins.user.id) for admins in chat_admins]
        sum_stat_chat_spoons = 0
        admins_links = ""
        for admin_id, admin_custom_title in zip(admins_ids, admins_custom_titles):
            c.execute("SELECT snow_spoons FROM users WHERE chat_id = ? AND user_id = ?", (chat_id, admin_id))
            stat_spoons = c.fetchone()
            if (stat_spoons is not None) & (admin_custom_title is not None):
                sum_stat_chat_spoons += stat_spoons[0]
                admins_links += (f'<a href="tg://user?id={admin_id}">{admin_custom_title + _members_emodzi_list[admin_id % 100] + " съел " + str(stat_spoons[0]) + " ложек снега"}</a>\n')
        sum_spoons_str = "Всего было съедено в чате " + str(sum_stat_chat_spoons) + " ложек снега"
        sum_spoons_str += "\nВстречайте лучших пожирателей!!\n"

        conn.close()
        await update.effective_chat.send_message(sum_spoons_str + admins_links, parse_mode='HTML')
#конец игрового кода
#конец игрового кода


commands = {
    'калл': call,
    'помощь': help,
    'help': help,
    'памагити': help,
    'список': show_admins,
    'список участников': show_admins,
    'чаты с ботом': show_chats,
    'снег': snow_command,
    'моя стата снега': show_snow_stats,
    'стата снега': allChat_snow_stats,
    'пинг': ping,
    'сизам откройся': add_users_in_bd
}

async def russian_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команд на русском языке"""
    message = update.message.text.lower().strip('/')
    command = commands.get(message, unknown)
    await command(update, context)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7460009035:AAFb_uzUkhiTQDp0mNtx68Ia6xVdPrRU9Hs").build()

    # Обработчик команд на русском языке
    start_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, russian_commands)
    application.add_handler(start_handler)

    # Keep track of which chats the bot is in
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(CommandHandler("show_chats", show_chats))
    application.add_handler(CommandHandler("show_admins", show_admins))

    application.add_handler(CommandHandler("call", call))

    application.add_handler(CommandHandler("help", help))

    # Handle members joining/leaving chats.
    application.add_handler(ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # Interpret any other command or text message as a start of a private chat.
    # This will record the user as being in a private chat with bot.
    application.add_handler(MessageHandler(filters.ALL, start_private_chat))

    # Run the bot until the user presses Ctrl-C
    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]`
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()