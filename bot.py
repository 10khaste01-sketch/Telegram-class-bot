import json
import os
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    ConversationHandler, CallbackContext
)

# مراحل کانورسیشن
CHOOSING, ADD_DAY, ADD_TIME, ADD_PRICE = range(4)

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

        update.message.reply_text(
            "\n".join(msg_lines),
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

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

    # ذخیره در فایل
    classes = load_classes()
    new_class = {
        "day": context.user_data["day"],
        "time": context.user_data["time"],
        "price": price,
        # این آیدی نمایش داده نمی‌شود
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

    # پاک کردن دیتا از حافظه موقت
    context.user_data.clear()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        "عملیات لغو شد. هر وقت خواستی /start رو بزن 🌱",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    # توکن از Environment Variable خوانده می‌شود
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not TOKEN:
        raise RuntimeError("متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است!")

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choose_option)],
            ADD_DAY: [MessageHandler(Filters.text & ~Filters.command, add_day)],
            ADD_TIME: [MessageHandler(Filters.text & ~Filters.command, add_time)],
            ADD_PRICE: [MessageHandler(Filters.text & ~Filters.command, add_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv_handler)

    # شروع ربات به صورت polling
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
