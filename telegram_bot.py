"""
Telegram Bot implementation based on LeakOSINT API Documentation
Reference: documentation.html (lines 201-303)
"""

import os
import sys
from random import randint
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
except ModuleNotFoundError:
    print("[!] telebot is not installed. To run this bot, install it via: pip install pyTelegramBotAPI")
    telebot = None

from leakosint_service import LeakOSINTClient, DEFAULT_API_URL

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API_TOKEN = os.environ.get("LEAKOSINT_API_TOKEN", "").strip()
DEFAULT_LANG = os.environ.get("LEAKOSINT_DEFAULT_LANG", "en")
DEFAULT_LIMIT = int(os.environ.get("LEAKOSINT_DEFAULT_LIMIT", 100))

# Cache reports for pagination
cash_reports = {}

client = LeakOSINTClient(token=API_TOKEN, api_url=DEFAULT_API_URL)


def user_access_test(user_id: int) -> bool:
    """Access control check for bot users."""
    return True


def generate_report(query: str, query_id: int, limit: int = DEFAULT_LIMIT, lang: str = DEFAULT_LANG):
    """Generates paginated report matching documentation logic."""
    global cash_reports
    clean_query = query.split("\n")[0].strip()
    
    res = client.search(
        query=clean_query,
        limit=limit,
        lang=lang,
        report_type="json",
    )

    if not res.get("success"):
        print(f"Error: {res.get('error')}")
        return None

    raw_response = res.get("raw_response", {})
    if not isinstance(raw_response, dict) or "List" not in raw_response:
        return ["<b>No results found</b>\n\nNo records match your query."]

    cash_reports[str(query_id)] = []
    db_dict = raw_response["List"]

    for database_name, db_info in db_dict.items():
        text = [f"<b>{database_name}</b>", ""]
        info_leak = db_info.get("InfoLeak", "") if isinstance(db_info, dict) else ""
        text.append(info_leak + "\n")

        if database_name != "No results found" and isinstance(db_info, dict):
            for report_data in db_info.get("Data", []):
                if isinstance(report_data, dict):
                    for column_name, val in report_data.items():
                        text.append(f"<b>{column_name}</b>: {val}")
                    text.append("")

        joined_text = "\n".join(text)
        if len(joined_text) > 3500:
            joined_text = (
                joined_text[:3500]
                + joined_text[3500:].split("\n")[0]
                + "\n\n<i>Some data did not fit this message</i>"
            )
        cash_reports[str(query_id)].append(joined_text)

    if not cash_reports[str(query_id)]:
        cash_reports[str(query_id)].append("<b>No results found</b>")

    return cash_reports[str(query_id)]


def create_inline_keyboard(query_id: int, page_id: int, count_page: int):
    """Creates inline keyboard for paging through breach databases."""
    markup = InlineKeyboardMarkup()
    if count_page <= 1:
        return markup
    if page_id < 0:
        page_id = count_page - 1
    elif page_id >= count_page:
        page_id = page_id % count_page

    markup.row_width = 3
    markup.add(
        InlineKeyboardButton(text="<<", callback_data=f"/page {query_id} {page_id - 1}"),
        InlineKeyboardButton(text=f"{page_id + 1}/{count_page}", callback_data="page_list"),
        InlineKeyboardButton(text=">>", callback_data=f"/page {query_id} {page_id + 1}"),
    )
    return markup


def main():
    if not telebot:
        sys.exit(1)

    if not BOT_TOKEN:
        print("[!] Warning: TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
        print("Please set TELEGRAM_BOT_TOKEN to launch the bot.")
        return

    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=["start", "help"])
    def send_welcome(message):
        welcome_text = (
            "👋 <b>Welcome to LeakOSINT Intelligence Bot!</b>\n\n"
            "Send any phone number, email, username, or name to search leaked breach databases.\n"
            "<i>Powered by LeakOSINT API</i>"
        )
        bot.reply_to(message, welcome_text, parse_mode="HTML")

    @bot.message_handler(func=lambda message: True)
    def handle_query(message):
        user_id = message.from_user.id
        if not user_access_test(user_id):
            bot.send_message(message.chat.id, "You have no access to the bot.")
            return

        if message.content_type == "text":
            query_id = randint(0, 9999999)
            bot.send_chat_action(message.chat.id, "typing")
            report = generate_report(message.text, query_id)
            if report is None:
                bot.reply_to(
                    message,
                    "⚠️ The service is currently unavailable or token is missing/invalid.",
                    parse_mode="Markdown"
                )
                return

            markup = create_inline_keyboard(query_id, 0, len(report))
            try:
                bot.send_message(message.chat.id, report[0], parse_mode="HTML", reply_markup=markup)
            except telebot.apihelper.ApiTelegramException:
                clean_text = report[0].replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                bot.send_message(message.chat.id, clean_text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: True)
    def callback_query(call: CallbackQuery):
        global cash_reports
        if call.data.startswith("/page "):
            parts = call.data.split(" ")
            if len(parts) >= 3:
                query_id, page_id = parts[1], int(parts[2])
                if query_id not in cash_reports:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="The results of the request have expired or were deleted.",
                    )
                else:
                    report = cash_reports[query_id]
                    count_pages = len(report)
                    if page_id < 0:
                        page_id = count_pages - 1
                    elif page_id >= count_pages:
                        page_id = 0
                    markup = create_inline_keyboard(int(query_id), page_id, count_pages)
                    try:
                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=report[page_id],
                            parse_mode="HTML",
                            reply_markup=markup,
                        )
                    except telebot.apihelper.ApiTelegramException:
                        clean_text = report[page_id].replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=clean_text,
                            reply_markup=markup,
                        )

    print("🤖 LeakOSINT Telegram Bot is running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
