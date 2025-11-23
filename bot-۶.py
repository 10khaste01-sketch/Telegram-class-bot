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

# States for ConversationHandler
CHOOSING, ADD_SUBJECT, ADD_DAY, ADD_TIME, ADD_DURATION, ADD_PRICE, ADD_COUNTER, SELECT_CLASS, CONFIRM_CLASS = range(9)

DATA_FILE = "classes.json"


def load_classes():
    """Load classes from local JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_classes(classes):
    """Save classes list to local JSON file."""
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
            "اسم درس را وارد کن:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADD_SUBJECT

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
            subject = c.get("subject", "نامشخص")
            day = c.get("day", "نامشخص")
            time = c.get("time", "نامشخص")
            duration = c.get("duration", "نامشخص")
            price = c.get("price", "نامشخص")
            line = f"{i}. درس: {subject} | روز: {day} | ساعت: {time} | مدت: {duration} | هزینه: {price}"
            lines.append(line)

        lines.append("\nبرای رزرو، شماره کلاس را بفرست.")
        update.message.reply_text("\n".join(lines))
        return SELECT_CLASS

    update.message.reply_text("لطفاً از دکمه‌ها استفاده کن.")
    return CHOOSING


def add_subject(update: Update, context: CallbackContext):
    context.user_data["subject"] = update.message.text.strip()
    update.message.reply_text("روز کلاس را وارد کن:")
    return ADD_DAY


def add_day(update: Update, context: CallbackContext):
    context.user_data["day"] = update.message.text.strip()
    update.message.reply_text("ساعت کلاس را وارد کن (مثال: 18:00):")
    return ADD_TIME


def add_time(update: Update, context: CallbackContext):
    context.user_data["time"] = update.message.text.strip()
    update.message.reply_text("مدت زمان کلاس را وارد کن (مثال: 90 دقیقه):")
    return ADD_DURATION


def add_duration(update: Update, context: CallbackContext):
    context.user_data["duration"] = update.message.text.strip()
    update.message.reply_text("هزینه کلاس را وارد کن (مثال: 150):")
    return ADD_PRICE


def add_price(update: Update, context: CallbackContext):
    context.user_data["price"] = update.message.text.strip()
    update.message.reply_text("شمارش این کلاس را وارد کن (این مورد فقط برای ادمین است):")
    return ADD_COUNTER


def add_counter(update: Update, context: CallbackContext):
    context.user_data["counter"] = update.message.text.strip()

    classes = load_classes()
    classes.append(
        {
            "subject": context.user_data.get("subject", ""),
            "day": context.user_data.get("day", ""),
            "time": context.user_data.get("time", ""),
            "duration": context.user_data.get("duration", ""),
            "price": context.user_data.get("price", ""),
            "counter": context.user_data.get("counter", ""),
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
    context.user_data["chosen_snapshot"] = chosen  # keep copy for admin text

    subject = chosen.get("subject", "نامشخص")
    day = chosen.get("day", "نامشخص")
    time = chosen.get("time", "نامشخص")
    duration = chosen.get("duration", "نامشخص")
    price = chosen.get("price", "نامشخص")

    summary = (
        "این کلاس را انتخاب کردی:\n"
        f"درس: {subject}\n"
        f"روز: {day}\n"
        f"ساعت: {time}\n"
        f"مدت: {duration}\n"
        f"هزینه: {price}\n\n"
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
        update.message.reply_text("لطفاً یکی از گزینه‌ها را انتخاب کن.")
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

    # پیام به ادمین (همراه با شمارش)
    admin_raw = os.getenv("ADMIN_CHAT_ID")
    if admin_raw:
        try:
            admin_id = int(admin_raw)
            student = update.effective_user
            student_username = (
                f"@{student.username}" if student.username else "ندارد"
            )
            teacher_username = (
                f"@{chosen['teacher_username']}"
                if chosen.get("teacher_username")
                else "ندارد"
            )

            subject = chosen.get("subject", "نامشخص")
            day = chosen.get("day", "نامشخص")
            time = chosen.get("time", "نامشخص")
            duration = chosen.get("duration", "نامشخص")
            price = chosen.get("price", "نامشخص")
            counter = chosen.get("counter", "نامشخص")

            text_admin = (
                "رزرو جدید کلاس:\n\n"
                f"درس: {subject}\n"
                f"روز: {day}\n"
                f"ساعت: {time}\n"
                f"مدت: {duration}\n"
                f"هزینه: {price}\n"
                f"شمارش: {counter}\n\n"
                f"هنرجو id: {student.id}\n"
                f"هنرجو username: {student_username}\n\n"
                f"استاد id: {chosen.get('teacher_id', 'نامشخص')}\n"
                f"استاد username: {teacher_username}"
            )

            context.bot.send_message(chat_id=admin_id, text=text_admin)
        except Exception as e:
            print("Failed to notify admin:", e)

    context.user_data.clear()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        "عملیات لغو شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---- Simple web server for Render (health check) ----
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

    # start tiny web server in separate thread
    thread = threading.Thread(target=run_web_server, daemon=True)
    thread.start()

    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choose_option)],
            ADD_SUBJECT: [MessageHandler(Filters.text & ~Filters.command, add_subject)],
            ADD_DAY: [MessageHandler(Filters.text & ~Filters.command, add_day)],
            ADD_TIME: [MessageHandler(Filters.text & ~Filters.command, add_time)],
            ADD_DURATION: [MessageHandler(Filters.text & ~Filters.command, add_duration)],
            ADD_PRICE: [MessageHandler(Filters.text & ~Filters.command, add_price)],
            ADD_COUNTER: [MessageHandler(Filters.text & ~Filters.command, add_counter)],
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
