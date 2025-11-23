import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackContext
)

# مراحل کانورسیشن
CHOOSING, ADD_DAY, ADD_TIME, ADD_PRICE, SELECT_CLASS, CONFIRM_CLASS = range(6)

DATA_FILE = "classes.json"


def load_classes():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_classes(classes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)


def start(update: Update, context: CallbackContext):
    reply_keyboard = [["🧑‍🏫 گذاشتن کلاس", "🧑‍🎓 گرفتن کلاس"]]

    update.message.reply_text(
        "سلام! 👋\n"
        "لطفاً یکی از گزینه‌ها را انتخاب کن:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return CHOOSING


def choose_option(update: Update, context: CallbackContext):
    text = update.message.text

    if "گذاشتن کلاس" in text:
        update.message.reply_text(
            "خیلی هم عالی 🧑‍🏫\n"
            "لطفاً *روز کلاس* را وارد کن (مثلاً: شنبه، دوشنبه، ...):",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_DAY

    elif "گرفتن کلاس" in text:
        classes = load_classes()
        if not classes:
            update.message.reply_text(
                "هنوز هیچ کلاسی ثبت نشده 🥲",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        msg_lines = ["📚 لیست کلاس‌های موجود:"]
        for i, c in enumerate(classes, start=1):
            line = f"{i}. روز: {c['day']} | ساعت: {c['time']} | هزینه: {c['price']}"
            msg_lines.append(line)

        msg_lines.append("")
        msg_lines.append("برای رزرو، *شماره کلاس* مورد نظر را ارسال کن.")
        update.message.reply_text(
            "\n".join(msg_lines),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return SELECT_CLASS

    else:
        update.message.reply_text("لطفاً یکی از گزینه‌های منو را انتخاب کن.")
        return CHOOSING


def add_day(update: Update, context: CallbackContext):
    day = update.message.text.strip()
    context.user_data["day"] = day
    update.message.reply_text(
        f"روز کلاس: *{day}*\n"
        "حالا *ساعت کلاس* را وارد کن (مثلاً: 18:00):",
        parse_mode="Markdown",
    )
    return ADD_TIME


def add_time(update: Update, context: CallbackContext):
    time = update.message.text.strip()
    context.user_data["time"] = time
    update.message.reply_text(
        f"ساعت کلاس: *{time}*\n"
        "حالا *هزینه کلاس* را وارد کن (مثلاً: 150):",
        parse_mode="Markdown",
    )
    return ADD_PRICE


def add_price(update: Update, context: CallbackContext):
    price = update.message.text.strip()
    context.user_data["price"] = price

    classes = load_classes()
    new_class = {
        "day": context.user_data["day"],
        "time": context.user_data["time"],
        "price": price,
        "teacher_id": update.effective_user.id,
        "teacher_username": update.effective_user.username,
    }
    classes.append(new_class)
    save_classes(classes)

    update.message.reply_text(
        "کلاس با موفقیت ثبت شد ✅\n"
        "ممنون 🙏",
        reply_markup=ReplyKeyboardRemove()
    )

    context.user_data.clear()
    return ConversationHandler.END


def select_class(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    classes = load_classes()
    if not classes:
        update.message.reply_text(
            "در حال حاضر هیچ کلاسی موجود نیست.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    try:
        idx = int(text) - 1
    except ValueError:
        update.message.reply_text("لطفاً *فقط شماره کلاس* را به صورت عدد وارد کن.", parse_mode="Markdown")
        return SELECT_CLASS

    if idx < 0 or idx >= len(classes):
        update.message.reply_text("چنین شماره کلاسی وجود ندارد. لطفاً دوباره امتحان کن.")
        return SELECT_CLASS

    chosen = classes[idx]
    context.user_data["class_index"] = idx
    context.user_data["class_snapshot"] = chosen  # برای نمایش به کاربر

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
    kb = [["بله، این کلاس را می‌خواهم", "نه، منصرف شدم"]]
    update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )
    return CONFIRM_CLASS


def confirm_class(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if "بله" in text:
        classes = load_classes()
        idx = context.user_data.get("class_index")

        if idx is None or idx < 0 or idx >= len(classes):
            update.message.reply_text(
                "متأسفانه این کلاس دیگر در لیست موجود نیست (شاید قبلاً رزرو شده باشد).",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data.clear()
            return ConversationHandler.END

        chosen = classes.pop(idx)
        save_classes(classes)

        # پیام به هنرجو
        update.message.reply_text(
            "رزرو کلاس شما ثبت شد ✅
"
            "استاد به زودی با شما هماهنگ می‌کند.",
            reply_markup=ReplyKeyboardRemove()
        )

        # پیام به ادمین (اگر تنظیم شده باشد)
        admin_chat_id = os.environ.get("ADMIN_CHAT_ID")
        if admin_chat_id:
            try:
                admin_text = (
                    "یک رزرو کلاس جدید ثبت شد 👇

"
                    f"روز: {chosen['day']}
"
                    f"ساعت: {chosen['time']}
"
                    f"هزینه: {chosen['price']}

"
                    f"آیدی هنرجو: {update.effective_user.id}
"
                    f"یوزرنیم هنرجو: @{update.effective_user.username if update.effective_user.username else 'ندارد'}
"
                    f"آیدی استاد: {chosen.get('teacher_id')}
"
                    f"یوزرنیم استاد: @{chosen.get('teacher_username') or 'ندارد'}"
                )
                update.get_bot().send_message(chat_id=int(admin_chat_id), text=admin_text)
            except Exception as e:
                # فقط لاگ در سرور، به کاربر چیزی نگیم
                print(f"Failed to notify admin: {e}")

        context.user_data.clear()
        return ConversationHandler.END

    elif "نه" in text:
        update.message.reply_text(
            "رزرو لغو شد. هر وقت خواستی می‌تونی دوباره /start را بفرستی 🌱",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    else:
        update.message.reply_text(
            "لطفاً یکی از گزینه‌های کیبورد را انتخاب کن.",
        )
        return CONFIRM_CLASS


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        "عملیات لغو شد. هر وقت خواستی /start رو بزن 🌱",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# وب‌سرور خیلی ساده فقط برای این‌که یک پورت باز باشد (برای Render)
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
        raise RuntimeError("متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است!")

    # اجرای وب‌سرور در ترد جداگانه
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
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

    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
