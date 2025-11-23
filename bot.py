import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackContext
)

# States
CHOOSING, ADD_DAY, ADD_TIME, ADD_PRICE, SELECT_CLASS, CONFIRM_CLASS = range(6)

DATA_FILE = "classes.json"


def load_classes():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


def save_classes(classes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)


def start(update: Update, context: CallbackContext):
    kb = [["🧑‍🏫 گذاشتن کلاس", "🧑‍🎓 گرفتن کلاس"]]
    update.message.reply_text(
        "سلام! یکی از گزینه‌ها را انتخاب کن:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return CHOOSING


def choose_option(update: Update, context: CallbackContext):
    t = update.message.text

    if "گذاشتن کلاس" in t:
        update.message.reply_text(
            "روز کلاس را وارد کن:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_DAY

    elif "گرفتن کلاس" in t:
        classes = load_classes()
        if not classes:
            update.message.reply_text("هیچ کلاسی ثبت نشده.")
            return ConversationHandler.END

        msg = "📚 لیست کلاس‌های موجود:

"
        for i, c in enumerate(classes, start=1):
            msg += f"{i}. روز: {c['day']} | ساعت: {c['time']} | هزینه: {c['price']}
"
        msg += "
برای رزرو، شماره کلاس را بفرست."

        update.message.reply_text(msg)
        return SELECT_CLASS

    else:
        update.message.reply_text("یکی از گزینه‌ها را بزن.")
        return CHOOSING


def add_day(update: Update, context: CallbackContext):
    context.user_data["day"] = update.message.text.strip()
    update.message.reply_text("ساعت کلاس را وارد کن:")
    return ADD_TIME


def add_time(update: Update, context: CallbackContext):
    context.user_data["time"] = update.message.text.strip()
    update.message.reply_text("هزینه کلاس را وارد کن:")
    return ADD_PRICE


def add_price(update: Update, context: CallbackContext):
    context.user_data["price"] = update.message.text.strip()

    classes = load_classes()
    classes.append({
        "day": context.user_data["day"],
        "time": context.user_data["time"],
        "price": context.user_data["price"],
        "teacher_id": update.effective_user.id,
        "teacher_username": update.effective_user.username
    })
    save_classes(classes)

    update.message.reply_text("کلاس ذخیره شد ✅")
    return ConversationHandler.END


def select_class(update: Update, context: CallbackContext):
    classes = load_classes()
    try:
        idx = int(update.message.text) - 1
        if idx < 0 or idx >= len(classes):
            raise ValueError
    except:
        update.message.reply_text("شماره معتبر نیست.")
        return SELECT_CLASS

    chosen = classes[idx]
    context.user_data["idx"] = idx

    summary = (
        "این کلاس را انتخاب کردی:
"
        f"روز: {chosen['day']}
"
        f"ساعت: {chosen['time']}
"
        f"هزینه: {chosen['price']}

"
        "آیا این کلاس را می‌خوای؟"
    )

    kb = [["بله", "نه"]]
    update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

    return CONFIRM_CLASS


def confirm_class(update: Update, context: CallbackContext):
    if update.message.text == "نه":
        update.message.reply_text("لغو شد.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    classes = load_classes()
    idx = context.user_data["idx"]
    chosen = classes.pop(idx)
    save_classes(classes)

    update.message.reply_text(
        "رزرو انجام شد ✅",
        reply_markup=ReplyKeyboardRemove()
    )

    admin = os.environ.get("ADMIN_CHAT_ID")
    if admin:
        try:
            msg = (
                "🔥 رزرو جدید:
"
                f"روز: {chosen['day']}
"
                f"ساعت: {chosen['time']}
"
                f"هزینه: {chosen['price']}

"
                f"هنرجو: {update.effective_user.id}
"
                f"یوزرنیم: @{update.effective_user.username}"
            )
            update.get_bot().send_message(int(admin), msg)
        except:
            pass

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("لغو شد.")
    return ConversationHandler.END


# ------- Web Server for Render -------
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
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("TOKEN missing")

    threading.Thread(target=run_web_server, daemon=True).start()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choose_option)],
                ADD_DAY: [MessageHandler(Filters.text & ~Filters.command, add_day)],
                ADD_TIME: [MessageHandler(Filters.text & ~Filters.command, add_time)],
                ADD_PRICE: [MessageHandler(Filters.text & ~Filters.command, add_price)],
                SELECT_CLASS: [MessageHandler(Filters.text & ~Filters.command, select_class)],
                CONFIRM_CLASS: [MessageHandler(Filters.text & ~Filters.command, confirm_class)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
    )

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
