import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

# Conversation states
CHOOSING, ADD_DAY, ADD_TIME, ADD_PRICE = range(4)

DATA_FILE = "classes.json"


def load_classes():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_classes(classes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)


def start(update: Update, context: CallbackContext):
    keyboard = [["Add class", "View classes"]]
    update.message.reply_text(
        "Hi! Please choose an option:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return CHOOSING


def choose_option(update: Update, context: CallbackContext):
    text = update.message.text

    if text == "Add class":
        update.message.reply_text(
            "Send class day (example: Saturday):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADD_DAY

    if text == "View classes":
        classes = load_classes()
        if not classes:
            update.message.reply_text("No classes saved yet.")
            return ConversationHandler.END

        msg_lines = ["Classes list:"]
        for i, c in enumerate(classes, start=1):
            msg_lines.append(
                f"{i}. Day: {c['day']} | Time: {c['time']} | Price: {c['price']}"
            )

        update.message.reply_text(" ".join(msg_lines))
        return ConversationHandler.END

    update.message.reply_text("Use the keyboard buttons.")
    return CHOOSING


def add_day(update: Update, context: CallbackContext):
    context.user_data["day"] = update.message.text.strip()
    update.message.reply_text("Now send the class time (example: 18:00):")
    return ADD_TIME


def add_time(update: Update, context: CallbackContext):
    context.user_data["time"] = update.message.text.strip()
    update.message.reply_text("Now send the class price (example: 150):")
    return ADD_PRICE


def add_price(update: Update, context: CallbackContext):
    context.user_data["price"] = update.message.text.strip()

    classes = load_classes()
    classes.append(
        {
            "day": context.user_data["day"],
            "time": context.user_data["time"],
            "price": context.user_data["price"],
            "teacher_id": update.effective_user.id,
            "teacher_username": update.effective_user.username,
        }
    )

    save_classes(classes)
    update.message.reply_text("Class saved successfully.")
    context.user_data.clear()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


# ---------- Web server for Render ----------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing!")

    thread = threading.Thread(target=run_web_server, daemon=True)
    thread.start()

    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choose_option)],
            ADD_DAY: [MessageHandler(Filters.text & ~Filters.command, add_day)],
            ADD_TIME: [MessageHandler(Filters.text & ~Filters.command, add_time)],
            ADD_PRICE: [MessageHandler(Filters.text & ~Filters.command, add_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
