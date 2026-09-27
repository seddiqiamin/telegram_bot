import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import BOT_TOKEN, ADMIN_ID

from database import (
    create_tables,
    add_user,
    get_group,
    add_group,
    get_today_attendance,
    create_today_attendance,
    update_exit,
    update_group_settings,
    get_all_users,
    get_daily_report,
    get_monthly_user_report
)


# ============================================================
# زمان افغانستان
# ============================================================

AFGHANISTAN_TZ = ZoneInfo("Asia/Kabul")


def get_current_datetime():
    """
    زمان فعلی سرور + 4 ساعت و 30 دقیقه
    """
    return datetime.now() + timedelta(
        hours=4,
        minutes=30
    )


def get_current_date():
    """
    تاریخ امروز افغانستان
    """
    return get_current_datetime().strftime("%Y-%m-%d")


def get_current_time():
    """
    ساعت فعلی افغانستان به صورت 12 ساعته
    """
    now = get_current_datetime()

    hour = now.strftime("%I:%M")
    period = "قبل از ظهر" if now.hour < 12 else "بعد از ظهر"

    return f"{hour} {period}"


def format_time_12h(time_str):
    """
    تبدیل ساعت 24 ساعته به 12 ساعته برای نمایش
    مثال: 17:00 -> 05:00 بعد از ظهر
    """
    try:
        hour, minute = map(int, time_str.split(":"))

        period = "قبل از ظهر" if hour < 12 else "بعد از ظهر"

        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12

        return f"{hour_12:02d}:{minute:02d} {period}"

    except (ValueError, AttributeError):
        return time_str


def time_to_minutes(time_string):
    """
    تبدیل HH:MM به دقیقه
    برای مقایسه دقیق ساعت
    """

    try:
        hour, minute = map(
            int,
            time_string.split(":")
        )

        return hour * 60 + minute

    except (ValueError, AttributeError):
        return 0


# ============================================================
# دریافت Group ID و Topic ID
# ============================================================

def get_chat_topic(update):

    message = update.effective_message

    if not message:
        return None, None

    group_id = message.chat_id

    topic_id = message.message_thread_id

    if topic_id is None:
        topic_id = 0

    return group_id, topic_id


# ============================================================
# /start
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    add_user(
        user_id=user.id,
        name=user.full_name
    )

    await update.effective_message.reply_text(
        f"سلام {user.first_name} 👋\n\n"
        "اطلاعات شما با موفقیت ثبت شد. ✅\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 شناسه کاربری: {user.id}"
    )


# ============================================================
# تست زمان
# ============================================================

async def time_test(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    now = get_current_datetime()

    utc_now = now.astimezone(
        ZoneInfo("UTC")
    )

    await message.reply_text(
        f"🕐 زمان ربات\n\n"
        f"📅 تاریخ افغانستان: "
        f"{now.strftime('%Y-%m-%d')}\n"
        f"⏰ ساعت افغانستان: "
        f"{now.strftime('%H:%M:%S')}\n"
        f"🌍 منطقه زمانی: "
        f"{now.tzname()}\n\n"
        f"🕓 زمان UTC:\n"
        f"{utc_now.strftime('%Y-%m-%d %H:%M:%S')}"
    )


# ============================================================
# اطلاعات گروه
# ============================================================

async def group_info(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        f"🏢 اطلاعات گروه\n\n"
        f"نام گروه: {message.chat.title}\n"
        f"Group ID: {message.chat_id}\n"
        f"نوع: {message.chat.type}"
    )


# ============================================================
# اطلاعات Topic
# ============================================================

async def topic_info(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    topic_id = message.message_thread_id

    if topic_id is None:
        topic_id = 0

    await message.reply_text(
        f"📌 اطلاعات Topic\n\n"
        f"Group ID: {message.chat_id}\n"
        f"Topic ID: {topic_id}"
    )


# ============================================================
# ثبت خودکار گروه و Topic
# ============================================================

def ensure_group_exists(message):

    group_id = message.chat_id

    topic_id = message.message_thread_id

    if topic_id is None:
        topic_id = 0

    group = get_group(
        group_id,
        topic_id
    )

    if not group:

        add_group(
            group_id=group_id,
            group_name=message.chat.title or "بدون نام",
            topic_id=topic_id
        )

        group = get_group(
            group_id,
            topic_id
        )

    return group


# ============================================================
# حضور و غیاب
# ============================================================

async def attendance_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    # فقط گروه و سوپرگروه
    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    # متن پیام یا کپشن عکس
    text = message.text or message.caption

    if not text:
        return

    text = " ".join(
        text.strip().split()
    )

    # کاربر
    user = message.from_user

    if not user:
        return

    # ثبت کاربر
    add_user(
        user_id=user.id,
        name=user.full_name
    )

    # --------------------------------------------------------
    # Group / Topic
    # --------------------------------------------------------

    group_id = message.chat_id

    topic_id = message.message_thread_id

    if topic_id is None:
        topic_id = 0

    # --------------------------------------------------------
    # ثبت خودکار گروه
    # --------------------------------------------------------

    group = ensure_group_exists(message)

    if not group:

        await message.reply_text(
            "❌ خطا در ثبت گروه."
        )

        return

    (
        db_group_id,
        group_name,
        db_topic_id,
        entry_time,
        exit_time,
        late_entry_fine,
        early_exit_fine,
        status
    ) = group

    # اگر گروه غیرفعال باشد
    if status != "active":
        return

    # --------------------------------------------------------
    # زمان افغانستان
    # --------------------------------------------------------

    today = get_current_date()

    current_time = get_current_time()

    # ========================================================
    # ورود
    # ========================================================

    if text in [
        "سلام",
        "سلام!",
        "سلام !"
    ]:

        attendance = get_today_attendance(
            user_id=user.id,
            group_id=group_id,
            topic_id=topic_id,
            date=today
        )

        # قبلاً ورود ثبت شده
        if attendance:

            await message.reply_text(
                f"⚠️ ورود شما قبلاً ثبت شده است.\n\n"
                f"👤 {user.full_name}\n"
                f"🕐 زمان ورود: {attendance[5]}"
            )

            return

        # ----------------------------------------------------
        # محاسبه جریمه ورود
        # ----------------------------------------------------

        entry_fine = 0

        if (
            time_to_minutes(current_time)
            >
            time_to_minutes(entry_time)
        ):

            entry_fine = late_entry_fine

        # ----------------------------------------------------
        # ذخیره ورود
        # ----------------------------------------------------

        create_today_attendance(
            user_id=user.id,
            group_id=group_id,
            topic_id=topic_id,
            date=today,
            entry_time=current_time,
            entry_fine=entry_fine
        )

        # ----------------------------------------------------
        # پیام ورود
        # ----------------------------------------------------

        if entry_fine > 0:

            await message.reply_text(
                f"⚠️ ورود ثبت شد\n\n"
                f"👤 {user.full_name}\n"
                f"🕐 زمان ورود: {current_time}\n"
                f"⏰ ساعت تعیین‌شده: {entry_time}\n\n"
                f"💰 جریمه تأخیر: "
                f"{entry_fine} افغانی"
            )

        else:

            await message.reply_text(
                f"🟢 ورود ثبت شد\n\n"
                f"👤 {user.full_name}\n"
                f"🕐 زمان ورود: {current_time}\n"
                f"⏰ ساعت تعیین‌شده: {entry_time}\n\n"
                f"💰 جریمه: 0 افغانی"
            )

        return

    # ========================================================
    # خروج
    # ========================================================

    if text in [
        "خدا حافظ",
        "خداحافظ",
        "خدا حافظ!",
        "خداحافظ!"
    ]:

        attendance = get_today_attendance(
            user_id=user.id,
            group_id=group_id,
            topic_id=topic_id,
            date=today
        )

        # ورود ثبت نشده
        if not attendance:

            await message.reply_text(
                "⚠️ برای امروز ورود شما ثبت نشده است.\n\n"
                "ابتدا باید ورود خود را ثبت کنید."
            )

            return

        # خروج قبلاً ثبت شده
        if attendance[6]:

            await message.reply_text(
                f"⚠️ خروج شما قبلاً ثبت شده است.\n\n"
                f"🕐 زمان خروج: {attendance[6]}"
            )

            return

        # ----------------------------------------------------
        # محاسبه جریمه خروج
        # ----------------------------------------------------

        exit_fine = 0

        if (
            time_to_minutes(current_time)
            <
            time_to_minutes(exit_time)
        ):

            exit_fine = early_exit_fine

        # ----------------------------------------------------
        # ذخیره خروج
        # ----------------------------------------------------

        update_exit(
            attendance_id=attendance[0],
            exit_time=current_time,
            exit_fine=exit_fine
        )

        # ----------------------------------------------------
        # پیام خروج
        # ----------------------------------------------------

        if exit_fine > 0:

            await message.reply_text(
                f"⚠️ خروج ثبت شد\n\n"
                f"👤 {user.full_name}\n"
                f"🕐 زمان خروج: {current_time}\n"
                f"⏰ ساعت تعیین‌شده: {exit_time}\n\n"
                f"💰 جریمه خروج زودهنگام: "
                f"{exit_fine} افغانی"
            )

        else:

            await message.reply_text(
                f"🔵 خروج ثبت شد\n\n"
                f"👤 {user.full_name}\n"
                f"🕐 زمان خروج: {current_time}\n"
                f"⏰ ساعت تعیین‌شده: {exit_time}\n\n"
                f"💰 جریمه: 0 افغانی"
            )

        return


# ============================================================
# پنل مدیریت
# ============================================================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    message = update.effective_message

    if not user or not message:
        return

    if user.id != ADMIN_ID:

        await message.reply_text(
            "⛔ شما دسترسی به پنل مدیریت ندارید."
        )

        return

    # فقط گروه
    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        await message.reply_text(
            "⚠️ برای مدیریت تنظیمات، "
            "دستور /admin را داخل Topic "
            "حضور و غیاب گروه اجرا کنید."
        )

        return

    # ثبت گروه
    ensure_group_exists(message)

    topic_id = message.message_thread_id or 0

    keyboard = [
        [
            InlineKeyboardButton(
                "⚙️ تنظیمات حاضری",
                callback_data="attendance_settings"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 مدیریت کاربران",
                callback_data="manage_users"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 گزارش امروز",
                callback_data="daily_report"
            )
        ],
        [
            InlineKeyboardButton(
                "📅 گزارش ماهانه",
                callback_data="monthly_report"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 مجموع جریمه‌ها",
                callback_data="total_fines"
            )
        ]
    ]

    await message.reply_text(
        "👨‍💼 پنل مدیریت\n\n"
        f"🏢 گروه: {message.chat.title}\n"
        f"📌 Topic ID: {topic_id}\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# Callback های مدیریت
# ============================================================

async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    user = query.from_user

    if user.id != ADMIN_ID:

        await query.answer(
            "⛔ شما دسترسی ندارید.",
            show_alert=True
        )

        return

    await query.answer()

    message = query.message

    if not message:
        return

    # --------------------------------------------------------
    # Group / Topic
    # --------------------------------------------------------

    group_id = message.chat_id

    topic_id = message.message_thread_id

    if topic_id is None:
        topic_id = 0

    # ========================================================
    # تنظیمات حاضری
    # ========================================================

    if query.data == "attendance_settings":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🕐 ساعت ورود",
                    callback_data="set_entry_time"
                )
            ],
            [
                InlineKeyboardButton(
                    "🕐 ساعت خروج",
                    callback_data="set_exit_time"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 جریمه ورود دیر",
                    callback_data="set_late_fine"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 جریمه خروج زود",
                    callback_data="set_early_fine"
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 مشاهده تنظیمات",
                    callback_data="show_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_admin"
                )
            ]
        ]

        await query.message.edit_text(
            "⚙️ تنظیمات حاضری\n\n"
            f"🏢 گروه: {message.chat.title}\n"
            f"📌 Topic ID: {topic_id}\n\n"
            "گزینه موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # مدیریت کاربران
    # ========================================================

    if query.data == "manage_users":

        users = get_all_users()

        if not users:

            text = "👥 هیچ کاربری ثبت نشده است."

        else:

            text = "👥 کاربران ثبت‌شده\n\n"

            for number, user_data in enumerate(
                users,
                start=1
            ):

                user_id = user_data[0]

                name = user_data[1]

                status = user_data[2]

                status_text = (
                    "فعال ✅"
                    if status == "active"
                    else "غیرفعال ❌"
                )

                text += (
                    f"{number}. {name}\n"
                    f"🆔 {user_id}\n"
                    f"📌 {status_text}\n\n"
                )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_admin"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # گزارش امروز
    # ========================================================

    if query.data == "daily_report":

        today = get_current_date()

        report = get_daily_report(
            group_id,
            topic_id,
            today
        )

        if not report:

            text = (
                "📊 گزارش امروز\n\n"
                f"📅 {today}\n\n"
                "هنوز اطلاعاتی ثبت نشده است."
            )

        else:

            text = (
                "📊 گزارش امروز\n\n"
                f"📅 {today}\n"
                f"🏢 {message.chat.title}\n"
                f"📌 Topic: {topic_id}\n\n"
            )

            total_fine = 0

            for number, row in enumerate(
                report,
                start=1
            ):

                name = row[0]

                entry = row[1] or "ثبت نشده"

                exit_time = row[2] or "ثبت نشده"

                entry_fine = row[3] or 0

                exit_fine = row[4] or 0

                fine = entry_fine + exit_fine

                total_fine += fine

                text += (
                    f"{number}️⃣ {name}\n"
                    f"🟢 ورود: {entry}\n"
                    f"🔵 خروج: {exit_time}\n"
                    f"💰 جریمه: {fine} افغانی\n\n"
                )

            text += (
                "━━━━━━━━━━━━\n"
                f"💰 مجموع جریمه: "
                f"{total_fine} افغانی"
            )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_admin"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # گزارش ماهانه
    # ========================================================

    if query.data == "monthly_report":

        now = get_current_datetime()

        year = now.year

        month = now.month

        users = get_all_users()

        text = (
            "📅 گزارش ماهانه حضور و غیاب\n\n"
            f"📆 {year}-{month:02d}\n"
            f"🏢 {message.chat.title}\n"
            f"📌 Topic: {topic_id}\n\n"
        )

        total_fine_all = 0

        for number, user_data in enumerate(
            users,
            start=1
        ):

            user_id = user_data[0]

            name = user_data[1]

            report = get_monthly_user_report(
                user_id,
                group_id,
                topic_id,
                year,
                month
            )

            days = report[0] or 0

            late = report[1] or 0

            early = report[2] or 0

            entry_fine = report[3] or 0

            exit_fine = report[4] or 0

            total = entry_fine + exit_fine

            total_fine_all += total

            text += (
                f"{number}️⃣ {name}\n"
                f"📆 روزهای ثبت‌شده: {days}\n"
                f"🟡 ورود دیر: {late}\n"
                f"🔴 خروج زود: {early}\n"
                f"💰 جریمه ورود: {entry_fine} افغانی\n"
                f"💰 جریمه خروج: {exit_fine} افغانی\n"
                f"💵 مجموع: {total} افغانی\n\n"
            )

        text += (
            "━━━━━━━━━━━━\n"
            f"💰 مجموع جریمه‌ها: "
            f"{total_fine_all} افغانی"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_admin"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # مجموع جریمه‌ها
    # ========================================================

    if query.data == "total_fines":

        now = get_current_datetime()

        users = get_all_users()

        text = (
            "💰 مجموع جریمه‌ها\n\n"
            f"🏢 {message.chat.title}\n"
            f"📌 Topic: {topic_id}\n\n"
        )

        grand_total = 0

        for user_data in users:

            user_id = user_data[0]

            name = user_data[1]

            report = get_monthly_user_report(
                user_id,
                group_id,
                topic_id,
                now.year,
                now.month
            )

            entry_fine = report[3] or 0

            exit_fine = report[4] or 0

            total = entry_fine + exit_fine

            grand_total += total

            text += (
                f"👤 {name}\n"
                f"💵 {total} افغانی\n\n"
            )

        text += (
            "━━━━━━━━━━━━\n"
            f"💰 مجموع کل: "
            f"{grand_total} افغانی"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="back_admin"
                )
            ]
        ]

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # ========================================================
    # ساعت ورود
    # ========================================================

    if query.data == "set_entry_time":

        context.user_data["admin_action"] = "entry_time"

        context.user_data["admin_group_id"] = group_id

        context.user_data["admin_topic_id"] = topic_id

        await query.message.reply_text(
            "🕐 ساعت ورود جدید را ارسال کنید.\n\n"
            "مثال:\n"
            "08:00"
        )

        return

    # ========================================================
    # ساعت خروج
    # ========================================================

    if query.data == "set_exit_time":

        context.user_data["admin_action"] = "exit_time"

        context.user_data["admin_group_id"] = group_id

        context.user_data["admin_topic_id"] = topic_id

        await query.message.reply_text(
            "🕐 ساعت خروج جدید را ارسال کنید.\n\n"
            "مثال:\n"
            "17:00"
        )

        return

    # ========================================================
    # جریمه ورود
    # ========================================================

    if query.data == "set_late_fine":

        context.user_data["admin_action"] = "late_fine"

        context.user_data["admin_group_id"] = group_id

        context.user_data["admin_topic_id"] = topic_id

        await query.message.reply_text(
            "💰 مبلغ جریمه ورود دیر را ارسال کنید.\n\n"
            "مثال:\n"
            "50"
        )

        return

    # ========================================================
    # جریمه خروج
    # ========================================================

    if query.data == "set_early_fine":

        context.user_data["admin_action"] = "early_fine"

        context.user_data["admin_group_id"] = group_id

        context.user_data["admin_topic_id"] = topic_id

        await query.message.reply_text(
            "💰 مبلغ جریمه خروج زود را ارسال کنید.\n\n"
            "مثال:\n"
            "50"
        )

        return

    # ========================================================
    # مشاهده تنظیمات
    # ========================================================

    if query.data == "show_settings":

        group = get_group(
            group_id,
            topic_id
        )

        if not group:

            await query.message.reply_text(
                "⚠️ تنظیمات این Topic هنوز ثبت نشده است."
            )

            return

        (
            db_group_id,
            group_name,
            db_topic_id,
            entry_time,
            exit_time,
            late_fine,
            early_fine,
            status
        ) = group

        await query.message.reply_text(
            f"⚙️ تنظیمات حاضری\n\n"
            f"🏢 گروه: {group_name}\n"
            f"🆔 Group ID: {group_id}\n"
            f"📌 Topic ID: {topic_id}\n\n"
            f"🕐 ساعت ورود: {format_time_12h(entry_time)}\n"
            f"🕐 ساعت خروج: {format_time_12h(exit_time)}\n\n"
            f"💰 جریمه ورود دیر: "
            f"{late_fine} افغانی\n"
            f"💰 جریمه خروج زود: "
            f"{early_fine} افغانی\n\n"
            f"📌 وضعیت: {status}"
        )

        return

    # ========================================================
    # بازگشت
    # ========================================================

    if query.data == "back_admin":

        keyboard = [
            [
                InlineKeyboardButton(
                    "⚙️ تنظیمات حاضری",
                    callback_data="attendance_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 مدیریت کاربران",
                    callback_data="manage_users"
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 گزارش امروز",
                    callback_data="daily_report"
                )
            ],
            [
                InlineKeyboardButton(
                    "📅 گزارش ماهانه",
                    callback_data="monthly_report"
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 مجموع جریمه‌ها",
                    callback_data="total_fines"
                )
            ]
        ]

        await query.message.edit_text(
            "👨‍💼 پنل مدیریت\n\n"
            f"🏢 گروه: {message.chat.title}\n"
            f"📌 Topic ID: {topic_id}\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return


# ============================================================
# دریافت تنظیمات مدیر
# ============================================================

async def admin_setting_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    message = update.effective_message

    if not user or not message:
        return

    # فقط مدیر
    if user.id != ADMIN_ID:
        return

    action = context.user_data.get(
        "admin_action"
    )

    if not action:
        return

    if not message.text:
        return

    value = message.text.strip()

    group_id = context.user_data.get(
        "admin_group_id"
    )

    topic_id = context.user_data.get(
        "admin_topic_id"
    )

    if not group_id or topic_id is None:

        await message.reply_text(
            "❌ اطلاعات گروه پیدا نشد.\n"
            "لطفاً دوباره /admin را داخل Topic اجرا کنید."
        )

        context.user_data.pop(
            "admin_action",
            None
        )

        return

    # ========================================================
    # ساعت ورود
    # ========================================================

    if action == "entry_time":

        try:

            datetime.strptime(
                value,
                "%H:%M"
            )

        except ValueError:

            await message.reply_text(
                "❌ فرمت ساعت اشتباه است.\n\n"
                "فرمت صحیح:\n"
                "08:00"
            )

            return

        update_group_settings(
            group_id=group_id,
            topic_id=topic_id,
            entry_time=value
        )

        await message.reply_text(
            f"✅ ساعت ورود تغییر کرد.\n\n"
            f"🕐 ساعت جدید: {value}"
        )

    # ========================================================
    # ساعت خروج
    # ========================================================

    elif action == "exit_time":

        try:

            datetime.strptime(
                value,
                "%H:%M"
            )

        except ValueError:

            await message.reply_text(
                "❌ فرمت ساعت اشتباه است.\n\n"
                "فرمت صحیح:\n"
                "17:00"
            )

            return

        update_group_settings(
            group_id=group_id,
            topic_id=topic_id,
            exit_time=value
        )

        await message.reply_text(
            f"✅ ساعت خروج تغییر کرد.\n\n"
            f"🕐 ساعت جدید: {value}"
        )

    # ========================================================
    # جریمه ورود
    # ========================================================

    elif action == "late_fine":

        try:

            number = int(value)

            if number < 0:
                raise ValueError

        except ValueError:

            await message.reply_text(
                "❌ مبلغ نامعتبر است.\n\n"
                "فقط عدد وارد کنید.\n"
                "مثال: 50"
            )

            return

        update_group_settings(
            group_id=group_id,
            topic_id=topic_id,
            late_entry_fine=number
        )

        await message.reply_text(
            f"✅ جریمه ورود دیر تغییر کرد.\n\n"
            f"💰 مبلغ جدید: {number} افغانی"
        )

    # ========================================================
    # جریمه خروج
    # ========================================================

    elif action == "early_fine":

        try:

            number = int(value)

            if number < 0:
                raise ValueError

        except ValueError:

            await message.reply_text(
                "❌ مبلغ نامعتبر است.\n\n"
                "فقط عدد وارد کنید.\n"
                "مثال: 50"
            )

            return

        update_group_settings(
            group_id=group_id,
            topic_id=topic_id,
            early_exit_fine=number
        )

        await message.reply_text(
            f"✅ جریمه خروج زود تغییر کرد.\n\n"
            f"💰 مبلغ جدید: {number} افغانی"
        )

    # پاک کردن حالت
    context.user_data.pop(
        "admin_action",
        None
    )

    context.user_data.pop(
        "admin_group_id",
        None
    )

    context.user_data.pop(
        "admin_topic_id",
        None
    )


# ============================================================
# نمایش کاربران
# ============================================================

async def show_users(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    if user.id != ADMIN_ID:

        await update.effective_message.reply_text(
            "⛔ شما دسترسی ندارید."
        )

        return

    users = get_all_users()

    if not users:

        await update.effective_message.reply_text(
            "👥 هنوز هیچ کاربری ثبت نشده است."
        )

        return

    text = "👥 کاربران ثبت‌شده\n\n"

    for number, user_data in enumerate(
        users,
        start=1
    ):

        user_id = user_data[0]

        name = user_data[1]

        status = user_data[2]

        status_text = (
            "فعال ✅"
            if status == "active"
            else "غیرفعال ❌"
        )

        text += (
            f"{number}. {name}\n"
            f"🆔 {user_id}\n"
            f"📌 وضعیت: {status_text}\n\n"
        )

    await update.effective_message.reply_text(
        text
    )


# ============================================================
# گزارش روزانه
# ============================================================

async def daily_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    message = update.effective_message

    if not user or not message:
        return

    if user.id != ADMIN_ID:

        await message.reply_text(
            "⛔ شما دسترسی ندارید."
        )

        return

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        await message.reply_text(
            "⚠️ این دستور را داخل گروه اجرا کنید."
        )

        return

    group_id = message.chat_id

    topic_id = message.message_thread_id or 0

    ensure_group_exists(message)

    today = get_current_date()

    report = get_daily_report(
        group_id,
        topic_id,
        today
    )

    if not report:

        await message.reply_text(
            f"📊 گزارش حضور امروز\n\n"
            f"📅 تاریخ: {today}\n\n"
            "هنوز هیچ حضور و غیابی ثبت نشده است."
        )

        return

    text = (
        "📊 گزارش حضور امروز\n\n"
        f"📅 تاریخ: {today}\n"
        f"🏢 گروه: {message.chat.title}\n"
        f"📌 Topic: {topic_id}\n\n"
    )

    total_fine = 0

    total_people = 0

    for number, row in enumerate(
        report,
        start=1
    ):

        name = row[0]

        entry = row[1]

        exit_time = row[2]

        entry_fine = row[3] or 0

        exit_fine = row[4] or 0

        fine = entry_fine + exit_fine

        total_fine += fine

        total_people += 1

        text += (
            f"{number}️⃣ {name}\n"
            f"🟢 ورود: {entry or 'ثبت نشده'}\n"
            f"🔵 خروج: {exit_time or 'ثبت نشده'}\n"
            f"💰 جریمه: {fine} افغانی\n\n"
        )

    text += (
        "━━━━━━━━━━━━\n"
        f"👥 تعداد ثبت‌شده: {total_people}\n"
        f"💰 مجموع جریمه: {total_fine} افغانی"
    )

    await message.reply_text(
        text
    )


# ============================================================
# گزارش ماهانه
# ============================================================

async def monthly_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    message = update.effective_message

    if not user or not message:
        return

    if user.id != ADMIN_ID:

        await message.reply_text(
            "⛔ شما دسترسی ندارید."
        )

        return

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:

        await message.reply_text(
            "⚠️ این دستور را داخل گروه اجرا کنید."
        )

        return

    group_id = message.chat_id

    topic_id = message.message_thread_id or 0

    ensure_group_exists(message)

    now = get_current_datetime()

    users = get_all_users()

    if not users:

        await message.reply_text(
            "👥 هیچ کاربری ثبت نشده است."
        )

        return

    text = (
        "📅 گزارش ماهانه حضور و غیاب\n\n"
        f"📆 ماه: {now.year}-{now.month:02d}\n"
        f"🏢 گروه: {message.chat.title}\n"
        f"📌 Topic: {topic_id}\n\n"
    )

    total_fine_all = 0

    for number, user_data in enumerate(
        users,
        start=1
    ):

        user_id = user_data[0]

        name = user_data[1]

        report = get_monthly_user_report(
            user_id,
            group_id,
            topic_id,
            now.year,
            now.month
        )

        days = report[0] or 0

        late = report[1] or 0

        early = report[2] or 0

        entry_fine = report[3] or 0

        exit_fine = report[4] or 0

        total = entry_fine + exit_fine

        total_fine_all += total

        text += (
            f"{number}️⃣ {name}\n"
            f"📆 روزهای ثبت‌شده: {days}\n"
            f"🟡 ورود دیر: {late}\n"
            f"🔴 خروج زود: {early}\n"
            f"💰 جریمه ورود: {entry_fine} افغانی\n"
            f"💰 جریمه خروج: {exit_fine} افغانی\n"
            f"💵 مجموع: {total} افغانی\n\n"
        )

    text += (
        "━━━━━━━━━━━━\n"
        f"💰 مجموع جریمه همه کاربران: "
        f"{total_fine_all} افغانی"
    )

    await message.reply_text(
        text
    )


# ============================================================
# خطایابی
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "ERROR:",
        context.error
    )


# ============================================================
# اجرای ربات
# ============================================================

def main():

    # ایجاد جداول دیتابیس
    create_tables()

    # ساخت Application
    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ========================================================
    # دستورات
    # ========================================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_panel
        )
    )

    app.add_handler(
        CommandHandler(
            "users",
            show_users
        )
    )

    app.add_handler(
        CommandHandler(
            "groupinfo",
            group_info
        )
    )

    app.add_handler(
        CommandHandler(
            "topicinfo",
            topic_info
        )
    )

    app.add_handler(
        CommandHandler(
            "report",
            daily_report
        )
    )

    app.add_handler(
        CommandHandler(
            "monthly",
            monthly_report
        )
    )

    # تست زمان
    app.add_handler(
        CommandHandler(
            "time",
            time_test
        )
    )

    # ========================================================
    # دکمه‌های پنل مدیریت
    # ========================================================

    app.add_handler(
        CallbackQueryHandler(
            admin_callback
        )
    )

    # ========================================================
    # حضور و غیاب
    #
    # متن + عکس دارای کپشن
    # ========================================================

    app.add_handler(
        MessageHandler(
            (
                filters.TEXT
                | filters.PHOTO
            )
            & ~filters.COMMAND,
            attendance_handler
        ),
        group=1
    )

    # ========================================================
    # پیام‌های متنی مدیر
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin_setting_input
        ),
        group=2
    )

    # ========================================================
    # خطایابی
    # ========================================================

    app.add_error_handler(
        error_handler
    )

    # ========================================================
    # اجرای ربات
    # ========================================================

    print(
        "Attendance Bot Started..."
    )

    print(
        "Timezone: Asia/Kabul"
    )

    print(
        f"Current Afghanistan Time: "
        f"{get_current_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    asyncio.run(
        run_bot(app)
    )


# ============================================================
# اجرای Polling
# ============================================================

async def run_bot(app):

    await app.initialize()

    await app.start()

    await app.updater.start_polling(
        drop_pending_updates=False
    )

    try:

        await asyncio.Event().wait()

    except (
        KeyboardInterrupt,
        SystemExit
    ):

        pass

    finally:

        await app.updater.stop()

        await app.stop()

        await app.shutdown()


# ============================================================
# اجرای مستقیم
# ============================================================

if __name__ == "__main__":

    main()