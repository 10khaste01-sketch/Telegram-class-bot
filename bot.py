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
CHOOSING, ADD_DAY, ADD_TIME, ADD_PRICE, SELECT_CLASS, CONFIRM_CLASS = range(6)

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
    keyboard = [["گذاشتن کلاس", "گرفتن کلاس"]]
    update.message.reply_text(
        "سلام! یکی از گزینه‌ها را انتخاب کن:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return CHOOSING


def choose_option(update: Update, context: CallbackContext):
    text = update.message.text

    if "گذاشتن کلاس" in text:
        update.message.reply_text(
            "روز کلاس را وارد کن:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADD_DAY

    if "گرفتن کلاس" in text:
        classes = load_classes()
        if not classes:
            update.message.reply_text(
                "هنوز هیچ کلاسی ثبت نشده.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END

        lines = ["لیست کلاس‌های موجود:"]
        for i, c in enumerate(classes, start=1):
            line = f"{i}. روز: {c['day']} | ساعت: {c['time']} | هزینه: {c['price']}"
            lines.append(line)

        lines.append("")
        lines.append("برای رزرو، شماره کلاس را بفرست.")
        update.message.reply_text("\n".join(lines))
        return SELECT_CLASS

    update.message.reply_text("لطفا از دکمه‌ها استفاده کن.")
    return CHOOSING


def add_day(update: Update, context: CallbackContext):
    context.user_data["day"] = update.message.text.strip()
    update.message.reply_text("ساعت کلاس را وارد کن (مثال: 18:00):")
    return ADD_TIME


def add_time(update: Update, context: CallbackContext):
    context.user_data["time"] = update.message.text.strip()
    update.message.reply_text("هزینه کلاس را وارد کن (مثال: 150):")
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

    update.message.reply_text("کلاس با موفقیت ثبت شد.")
    context.user_data.clear()
    return ConversationHandler.END


def select_class(update: Update, context: CallbackContext):
    classes = load_classes()
    if not classes:
        update.message.reply_text("هیچ کلاسی موجود نیست.")
        return ConversationHandler.END

    text = update.message.text.strip()
    try:
        idx = int(text) - 1
        if idx < 0 or idx >= len(classes):
            raise ValueError
    except ValueError:
        update.message.reply_text("شماره کلاس نامعتبر است. دوباره بفرست.")
        return SELECT_CLASS

    chosen = classes[idx]
    context.user_data["idx"] = idx

    summary = (
        "این کلاس را انتخاب کردی:\n"
        f"روز: {chosen['day']}\n"
        f"ساعت: {chosen['time']}\n"
        f"هزینه: {chosen['price']}\n\n"
        "آیا این کلاس را می‌خواهی؟ (بله / نه)"
    )

    keyboard = [["بله", "نه"]]
    update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return CONFIRM_CLASS


def confirm_class(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if text == "نه":
        update.message.reply_text(
            "رزرو لغو شد.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    if text != "بله":
        update.message.reply_text("لطفا یکی از گزینه‌ها را انتخاب کن.")
        return CONFIRM_CLASS

    classes = load_classes()
    idx = context.user_data.get("idx")
    if idx is None or idx < 0 or idx >= len(classes):
        update.message.reply_text(
            "این کلاس دیگر در دسترس نیست.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    chosen = classes.pop(idx)
    save_classes(classes)

    # پیام به هنرجو
    update.message.reply_text(
        "رزرو کلاس شما با موفقیت انجام شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
# ارسال پیام به ادمین
admin_id = os.getenv("ADMIN_CHAT_ID")
if admin_id:
    admin_id = int(admin_id)
    student = update.effective_user

    username = f"@{student.username}" if student.username else "یوزرنیم ندارد"

    text_admin = (
        "🔥 رزرو جدید:\n"
        f"📅 روز: {chosen['day']}\n"
        f"⏰ ساعت: {chosen['time']}\n"
        f"💵 هزینه: {chosen['price']}\n"
        f"🧑‍🎓 هنرجو: {username}\n"
        f"🆔 آیدی عددی: {student.id}\n"
    )

    try:
        context.bot.send_message(chat_id=admin_id, text=text_admin)
    except Exception as e:
        print("❌ Error sending to admin:", e)

    context.user_data.clear()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        "عملیات لغو شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# Simple web server so Render sees an open port
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
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    # Start web server thread
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
            SELECT_CLASS: [MessageHandler(Filters.text & ~Filters.command, select_class)],
            CONFIRM_CLASS: [MessageHandler(Filters.text & ~Filters.command, confirm_class)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
