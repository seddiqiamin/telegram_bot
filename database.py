import sqlite3
from datetime import datetime

DB_NAME = "attendance.db"


# ==========================================
# اتصال به دیتابیس
# ==========================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# ==========================================
# ساخت جدول‌ها
# ==========================================

def create_tables():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------
    # کاربران
    # --------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------
    # گروه‌ها
    # --------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            topic_id INTEGER NOT NULL,

            entry_time TEXT DEFAULT '08:00',
            exit_time TEXT DEFAULT '17:00',

            late_entry_fine INTEGER DEFAULT 50,
            early_exit_fine INTEGER DEFAULT 50,

            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (group_id, topic_id)
        )
    """)

    # --------------------------------------
    # حضور و غیاب
    # --------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,

            date TEXT NOT NULL,

            entry_time TEXT,
            exit_time TEXT,

            entry_fine INTEGER DEFAULT 0,
            exit_fine INTEGER DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, group_id, topic_id, date)
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# کاربران
# ==========================================

def add_user(user_id, name):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (
            user_id,
            name
        )
        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            name = excluded.name
    """, (
        user_id,
        name
    ))

    conn.commit()
    conn.close()


def get_all_users():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            name,
            status
        FROM users
        ORDER BY name
    """)

    result = cursor.fetchall()

    conn.close()

    return result


# ==========================================
# گروه‌ها
# ==========================================

def add_group(
    group_id,
    group_name,
    topic_id
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO groups (
            group_id,
            group_name,
            topic_id
        )
        VALUES (?, ?, ?)

        ON CONFLICT(group_id, topic_id)
        DO UPDATE SET
            group_name = excluded.group_name
    """, (
        group_id,
        group_name,
        topic_id
    ))

    conn.commit()
    conn.close()


def get_group(group_id, topic_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            group_id,
            group_name,
            topic_id,
            entry_time,
            exit_time,
            late_entry_fine,
            early_exit_fine,
            status
        FROM groups
        WHERE group_id = ?
        AND topic_id = ?
    """, (
        group_id,
        topic_id
    ))

    result = cursor.fetchone()

    conn.close()

    return result


def get_all_groups():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            group_id,
            group_name,
            topic_id,
            entry_time,
            exit_time,
            late_entry_fine,
            early_exit_fine,
            status
        FROM groups
        ORDER BY group_name
    """)

    result = cursor.fetchall()

    conn.close()

    return result


def update_group_settings(
    group_id,
    topic_id,
    entry_time=None,
    exit_time=None,
    late_entry_fine=None,
    early_exit_fine=None
):

    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []

    if entry_time is not None:
        fields.append("entry_time = ?")
        values.append(entry_time)

    if exit_time is not None:
        fields.append("exit_time = ?")
        values.append(exit_time)

    if late_entry_fine is not None:
        fields.append("late_entry_fine = ?")
        values.append(late_entry_fine)

    if early_exit_fine is not None:
        fields.append("early_exit_fine = ?")
        values.append(early_exit_fine)

    if not fields:
        conn.close()
        return

    values.extend([
        group_id,
        topic_id
    ])

    query = f"""
        UPDATE groups
        SET {", ".join(fields)}
        WHERE group_id = ?
        AND topic_id = ?
    """

    cursor.execute(
        query,
        values
    )

    conn.commit()
    conn.close()


# ==========================================
# حضور امروز
# ==========================================

def get_today_attendance(
    user_id,
    group_id,
    topic_id,
    date
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            group_id,
            topic_id,
            date,
            entry_time,
            exit_time,
            entry_fine,
            exit_fine
        FROM attendance
        WHERE user_id = ?
        AND group_id = ?
        AND topic_id = ?
        AND date = ?
    """, (
        user_id,
        group_id,
        topic_id,
        date
    ))

    result = cursor.fetchone()

    conn.close()

    return result


def create_today_attendance(
    user_id,
    group_id,
    topic_id,
    date,
    entry_time,
    entry_fine=0
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attendance (
            user_id,
            group_id,
            topic_id,
            date,
            entry_time,
            entry_fine
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        group_id,
        topic_id,
        date,
        entry_time,
        entry_fine
    ))

    conn.commit()
    conn.close()


def update_exit(
    attendance_id,
    exit_time,
    exit_fine=0
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE attendance
        SET
            exit_time = ?,
            exit_fine = ?
        WHERE id = ?
    """, (
        exit_time,
        exit_fine,
        attendance_id
    ))

    conn.commit()
    conn.close()


# ==========================================
# گزارش روزانه
# ==========================================

def get_daily_report(
    group_id,
    topic_id,
    date
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            users.name,
            attendance.entry_time,
            attendance.exit_time,
            attendance.entry_fine,
            attendance.exit_fine

        FROM attendance

        INNER JOIN users
        ON users.user_id = attendance.user_id

        WHERE attendance.group_id = ?
        AND attendance.topic_id = ?
        AND attendance.date = ?

        ORDER BY attendance.entry_time
    """, (
        group_id,
        topic_id,
        date
    ))

    result = cursor.fetchall()

    conn.close()

    return result


# ==========================================
# گزارش ماهانه کاربر
# ==========================================

def get_monthly_user_report(
    user_id,
    group_id,
    topic_id,
    year,
    month
):

    conn = get_connection()
    cursor = conn.cursor()

    prefix = f"{year}-{month:02d}"

    cursor.execute("""
        SELECT

            COUNT(*),

            SUM(
                CASE
                    WHEN entry_fine > 0
                    THEN 1
                    ELSE 0
                END
            ),

            SUM(
                CASE
                    WHEN exit_fine > 0
                    THEN 1
                    ELSE 0
                END
            ),

            SUM(entry_fine),

            SUM(exit_fine)

        FROM attendance

        WHERE user_id = ?
        AND group_id = ?
        AND topic_id = ?
        AND date LIKE ?
    """, (
        user_id,
        group_id,
        topic_id,
        prefix + "%"
    ))

    result = cursor.fetchone()

    conn.close()

    return result