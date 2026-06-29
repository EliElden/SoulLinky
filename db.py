import sqlite3
from datetime import datetime, timedelta

# ==========================================
# НАСТРОЙКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ
# ==========================================

# check_same_thread=False необходим для многопоточных приложений (каким является telebot),
# чтобы разные потоки могли безопасно обращаться к одному файлу базы данных.
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()


def init_db():
    """
    Инициализирует базу данных при запуске бота.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            partner_id INTEGER,
            language TEXT DEFAULT 'ru' 
        )
    ''')

    # Таблица для черного списка
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            blocker_id INTEGER,
            blocked_id INTEGER,
            PRIMARY KEY (blocker_id, blocked_id)
        )
    ''')

    # Таблица для трекера настроения
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Важные даты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS important_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            is_annual INTEGER DEFAULT 0,
            remind_days_before INTEGER DEFAULT 7,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Отслеживание отправленных напоминаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders_sent (
            date_id INTEGER,
            reminder_year INTEGER,
            PRIMARY KEY (date_id, reminder_year)
        )
    ''')

    # Общий вишлист
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            creator_id INTEGER NOT NULL,
            wish_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для хранения серий сообщений подряд
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS streaks (
            user1_id INTEGER,
            user2_id INTEGER,
            streak_count INTEGER DEFAULT 0,
            last_streak_date TEXT,      -- дата, когда серия была обновлена (оба отправили в этот день)
            last_send_user1 TEXT,       -- дата последней отправки от user1
            last_send_user2 TEXT,       -- дата последней отправки от user2
            PRIMARY KEY (user1_id, user2_id)
        )
    ''')



    conn.commit()

    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    if 'username' not in existing_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN username TEXT')
        print("🔧 База данных обновлена: добавлена колонка 'username'")
        conn.commit()


def add_or_update_user(user_id, gender, username):
    """
    Добавляет нового пользователя или обновляет данные существующего.
    Вызывается при старте бота и при смене пола в настройках.
    """
    # Очищаем никнейм от знака '@', чтобы хранить его в едином чистом формате
    clean_username = username.replace('@', '') if username else None
    
    # ON CONFLICT используется для механизма "upsert" (update or insert):
    # Если юзера с таким user_id еще нет — добавляем.
    # Если он уже есть — просто обновляем ему пол и никнейм на свежие.
    cursor.execute('''
        INSERT INTO users (user_id, username, gender) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET 
            gender=excluded.gender, 
            username=excluded.username
    ''', (user_id, clean_username, gender))
    conn.commit()


def get_id_by_username(username):
    """
    Ищет числовой ID пользователя по его Telegram-никнейму.
    Возвращает ID, если найден, или None, если такого юзера нет в базе.
    """
    # Снова убираем '@', так как в базе ники хранятся без него
    clean_username = username.replace('@', '')
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
    result = cursor.fetchone()
    
    # Возвращаем первый элемент кортежа (сам ID), если результат есть
    return result[0] if result else None


def link_partners(user_id, partner_id):
    """
    Устанавливает двустороннюю связь между партнерами.
    Прописывает ID партнера крест-накрест для обоих пользователей.
    """
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (partner_id, user_id))
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (user_id, partner_id))
    conn.commit()


def get_gender(user_id):
    """
    Получает пол пользователя ('male' или 'female') по его ID.
    Возвращает None, если пользователь еще не зарегистрирован.
    """
    cursor.execute('SELECT gender FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_partner(user_id):
    """
    Узнает ID партнера для указанного пользователя.
    Возвращает ID партнера или None, если пользователь одинок.
    """
    cursor.execute('SELECT partner_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def unlink_partners(user_id):
    """
    Разрывает связь между партнерами.
    Очищает (ставит NULL) поле partner_id сразу у обоих пользователей.
    Возвращает ID бывшего партнера для отправки ему системного уведомления о разрыве.
    """
    partner_id = get_partner(user_id)
    if partner_id:
        # Обнуляем связь у инициатора разрыва
        cursor.execute('UPDATE users SET partner_id = NULL WHERE user_id = ?', (user_id,))
        # Обнуляем связь у его бывшего партнера
        cursor.execute('UPDATE users SET partner_id = NULL WHERE user_id = ?', (partner_id,))
        conn.commit()
        return partner_id
        
    return None

def get_all_users():
    """
    Возвращает список всех ID пользователей из базы данных для рассылки.
    """
    cursor.execute('SELECT user_id FROM users')
    # fetchall() возвращает список кортежей вида [(id1,), (id2,), ...]
    # Мы проходимся по нему циклом и достаем чистые ID
    return [row[0] for row in cursor.fetchall()]

def get_stats():
    """
    Возвращает статистику: общее кол-во пользователей и кол-во подтвержденных пар.
    Использует JOIN для проверки взаимности связи.
    """
    # 1. Считаем общее количество уникальных пользователей
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # 2. Считаем только взаимные пары (А привязан к Б, а Б к А)
    # Условие u1.user_id < u2.user_id нужно, чтобы не посчитать одну пару дважды
    cursor.execute('''
        SELECT COUNT(*) 
        FROM users u1
        JOIN users u2 ON u1.partner_id = u2.user_id
        WHERE u2.partner_id = u1.user_id AND u1.user_id < u2.user_id
    ''')
    total_pairs = cursor.fetchone()[0]
    
    return total_users, total_pairs

# --- ФУНКЦИИ ДЛЯ ЧЕРНОГО СПИСКА ---

def block_user(blocker_id, blocked_id):
    """Добавляет пользователя в черный список (игнорирует, если уже там)"""
    cursor.execute('INSERT OR IGNORE INTO blocked_users (blocker_id, blocked_id) VALUES (?, ?)', (blocker_id, blocked_id))
    conn.commit()

def unblock_user(blocker_id, blocked_id):
    """Удаляет пользователя из черного списка"""
    cursor.execute('DELETE FROM blocked_users WHERE blocker_id = ? AND blocked_id = ?', (blocker_id, blocked_id))
    conn.commit()

def is_blocked(blocker_id, blocked_id):
    """Проверяет, заблокировал ли blocker_id пользователя blocked_id"""
    cursor.execute('SELECT 1 FROM blocked_users WHERE blocker_id = ? AND blocked_id = ?', (blocker_id, blocked_id))
    return cursor.fetchone() is not None

def get_blocked_users(blocker_id):
    """Возвращает список заблокированных ID и их никнеймов (если есть)"""
    cursor.execute('''
        SELECT b.blocked_id, u.username
        FROM blocked_users b
        LEFT JOIN users u ON b.blocked_id = u.user_id
        WHERE b.blocker_id = ?
    ''', (blocker_id,))
    return cursor.fetchall()

def get_username(user_id):
    """
    Достает никнейм пользователя по его числовому ID.
    Возвращает никнейм (без @) или None, если у пользователя нет юзернейма.
    """
    cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] else None

# ==========================================
# ФУНКЦИИ ДЛЯ ВАЖНЫХ ДАТ
# ==========================================

def add_important_date(user_id, partner_id, title, event_date, is_annual, remind_days_before):
    """
    Добавляет общую важную дату для пары.
    user1_id — кто добавил, user2_id — партнёр.
    """
    cursor.execute('''
        INSERT INTO important_dates (user1_id, user2_id, title, event_date, is_annual, remind_days_before)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, partner_id, title, event_date, is_annual, remind_days_before))
    conn.commit()
    return cursor.lastrowid


def get_dates_for_user(user_id):
    """
    Возвращает все важные даты, где участвует пользователь.
    Возвращает список кортежей: (id, title, event_date, is_annual, remind_days_before)
    """
    cursor.execute('''
        SELECT id, title, event_date, is_annual, remind_days_before 
        FROM important_dates 
        WHERE user1_id = ? OR user2_id = ?
        ORDER BY event_date DESC
    ''', (user_id, user_id))
    return cursor.fetchall()


def delete_date(date_id, user_id):
    """
    Удаляет важную дату.
    Пользователь может удалить только ту дату, где он участвует (как user1 или user2).
    """
    cursor.execute('''
        DELETE FROM important_dates 
        WHERE id = ? AND (user1_id = ? OR user2_id = ?)
    ''', (date_id, user_id, user_id))
    conn.commit()
    return cursor.rowcount > 0  # True если удалили, False если не нашли


def get_dates_to_remind(today_date):
    """
    Возвращает список дат, о которых нужно напомнить сегодня.
    """

    cursor.execute('''
        SELECT d.id, d.user1_id, d.user2_id, d.title, d.event_date,
               d.is_annual, d.remind_days_before
        FROM important_dates d
        WHERE d.is_annual = 0
              AND date(d.event_date, '-' || d.remind_days_before || ' days') = ?

        UNION

        SELECT d.id, d.user1_id, d.user2_id, d.title, d.event_date,
               d.is_annual, d.remind_days_before
        FROM important_dates d
        WHERE d.is_annual = 1
              AND strftime('%m-%d', d.event_date) =
                  strftime('%m-%d', date(?, '+' || d.remind_days_before || ' days'))
    ''', (today_date, today_date))

    return cursor.fetchall()


def was_reminder_sent(date_id, year):
    """Проверяет, было ли уже отправлено напоминание в этом году"""
    cursor.execute('SELECT 1 FROM reminders_sent WHERE date_id = ? AND reminder_year = ?', (date_id, year))
    return cursor.fetchone() is not None


def mark_reminder_sent(date_id, year):
    """Отмечает, что напоминание за этот год отправлено"""
    cursor.execute('INSERT OR IGNORE INTO reminders_sent VALUES (?, ?)', (date_id, year))
    conn.commit()


# ==========================================
# ФУНКЦИИ ДЛЯ ОБЩЕГО ВИШЛИСТА
# ==========================================

def add_wish(user1_id, user2_id, creator_id, wish_type, title, description):
    cursor.execute('''
        INSERT INTO wishlist
        (user1_id, user2_id, creator_id, wish_type, title, description)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user1_id, user2_id, creator_id, wish_type, title, description))

    conn.commit()
    return cursor.lastrowid

def get_wishlist(user_id):
    cursor.execute('''
        SELECT w.id, w.wish_type, w.title, w.description,
               w.creator_id, u.username
        FROM wishlist w
        LEFT JOIN users u ON w.creator_id = u.user_id
        WHERE w.user1_id = ? OR w.user2_id = ?
        ORDER BY w.created_at DESC
    ''', (user_id, user_id))

    return cursor.fetchall()

def delete_wish(wish_id, user_id):
    cursor.execute('''
        DELETE FROM wishlist
        WHERE id = ?
        AND (user1_id = ? OR user2_id = ?)
    ''', (wish_id, user_id, user_id))

    conn.commit()
    return cursor.rowcount > 0

def update_streak(user_id, partner_id):
    """
    Обновляет серию (streak) для пары после отправки послания.
    user_id – кто отправил, partner_id – получатель.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    # Упорядочиваем ID, чтобы уникально идентифицировать пару
    if user_id < partner_id:
        u1, u2 = user_id, partner_id
    else:
        u1, u2 = partner_id, user_id

    # Получаем текущую запись о серии
    cursor.execute('''
        SELECT streak_count, last_streak_date, last_send_user1, last_send_user2
        FROM streaks WHERE user1_id = ? AND user2_id = ?
    ''', (u1, u2))
    row = cursor.fetchone()

    if row is None:
        # Если записи нет – создаём новую с нулевыми значениями
        streak_count = 0
        last_streak_date = None
        last_send_u1 = None
        last_send_u2 = None
    else:
        streak_count, last_streak_date, last_send_u1, last_send_u2 = row

    # Определяем, кто отправил, и обновляем его дату последней отправки
    if user_id == u1:
        last_send_u1 = today
        other_last_send = last_send_u2
    else:
        last_send_u2 = today
        other_last_send = last_send_u1

    # Проверяем, отправил ли другой пользователь сегодня
    both_sent_today = (last_send_u1 == today and last_send_u2 == today)

    new_streak = streak_count
    new_last_streak_date = last_streak_date

    if both_sent_today:
        # Если сегодня оба отправили – обновляем серию
        if last_streak_date is None:
            # Первая серия в истории
            new_streak = 1
            new_last_streak_date = today
        else:
            # Если серия уже обновлена сегодня – ничего не делаем
            if last_streak_date != today:
                # Проверяем, была ли серия вчера (продолжение)
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                if last_streak_date == yesterday:
                    new_streak = streak_count + 1
                else:
                    # Начинаем новую серию (предыдущая прервана)
                    new_streak = 1
                new_last_streak_date = today

    # Сохраняем обновлённую запись (INSERT OR REPLACE)
    cursor.execute('''
        INSERT OR REPLACE INTO streaks
        (user1_id, user2_id, streak_count, last_streak_date, last_send_user1, last_send_user2)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (u1, u2, new_streak, new_last_streak_date, last_send_u1, last_send_u2))
    conn.commit()


def get_streak(user_id, partner_id):
    """Возвращает текущее значение серии (количество дней подряд) для пары."""
    if user_id < partner_id:
        u1, u2 = user_id, partner_id
    else:
        u1, u2 = partner_id, user_id
    cursor.execute('SELECT streak_count FROM streaks WHERE user1_id = ? AND user2_id = ?', (u1, u2))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_wish_by_id(wish_id):
    cursor.execute('SELECT id, wish_type, title, description, creator_id FROM wishlist WHERE id = ?', (wish_id,))
    return cursor.fetchone()

def get_date_by_id(date_id):
    cursor.execute('SELECT id, title, event_date, is_annual, remind_days_before FROM important_dates WHERE id = ?', (date_id,))
    return cursor.fetchone()

def is_wish_owner(user_id, wish_id):
    cursor.execute('SELECT 1 FROM wishlist WHERE id = ? AND (user1_id = ? OR user2_id = ?)', (wish_id, user_id, user_id))
    return cursor.fetchone() is not None

def is_date_owner(user_id, date_id):
    cursor.execute('SELECT 1 FROM important_dates WHERE id = ? AND (user1_id = ? OR user2_id = ?)', (date_id, user_id, user_id))
    return cursor.fetchone() is not None

# ==========================================
# ФУНКЦИИ ДЛЯ МУД-ТРЕКЕРА
# ==========================================

def set_mood(user_id, mood):
    """Добавляет новую запись о настроении пользователя"""
    cursor.execute('''
        INSERT INTO moods (user_id, mood)
        VALUES (?, ?)
    ''', (user_id, mood))
    conn.commit()

def get_latest_mood(user_id):
    """Возвращает последнее установленное настроение пользователя и дату"""
    cursor.execute('''
        SELECT mood, created_at 
        FROM moods 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (user_id,))
    return cursor.fetchone()

def get_mood_stats(user_id):
    """Возвращает статистику: сколько раз было выбрано каждое настроение"""
    cursor.execute('''
        SELECT mood, COUNT(*) 
        FROM moods 
        WHERE user_id = ? 
        GROUP BY mood
    ''', (user_id,))
    # Превращаем результат [(mood, count), ...] в удобный словарь
    return dict(cursor.fetchall())

def get_mood_history(user1_id, user2_id, limit=15):
    """
    Возвращает историю настроений для пары (последние записи).
    Включает дату, время, ID, само настроение и никнейм.
    """
    cursor.execute('''
        SELECT m.user_id, m.mood, m.created_at, u.username
        FROM moods m
        LEFT JOIN users u ON m.user_id = u.user_id
        WHERE m.user_id IN (?, ?)
        ORDER BY m.created_at DESC
        LIMIT ?
    ''', (user1_id, user2_id, limit))
    return cursor.fetchall()