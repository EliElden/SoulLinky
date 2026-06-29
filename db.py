import sqlite3
from datetime import datetime, timedelta

class BaseDatabase:
    """
    @brief Базовый класс для работы с базой данных SQLite.
    @details Инкапсулирует логику подключения и управления транзакциями.
    """

    def __init__(self, db_path: str = 'database.db'):
        """
        @brief Конструктор базового класса БД.
        @param db_path Путь к файлу базы данных SQLite.
        """
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def commit(self):
        """
        @brief Фиксирует текущую транзакцию.
        """
        self.conn.commit()

    def close(self):
        """
        @brief Закрывает соединение с БД.
        """
        self.conn.close()


class BotDatabase(BaseDatabase):
    """
    @brief Класс для работы со специфичными таблицами Telegram-бота.
    @details Наследуется от BaseDatabase, реализуя все необходимые запросы (Repository).
    """

    def init_db(self):
        """
        @brief Инициализирует структуру базы данных при запуске бота.
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT,
                partner_id INTEGER,
                language TEXT DEFAULT 'ru' 
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_users (
                blocker_id INTEGER,
                blocked_id INTEGER,
                PRIMARY KEY (blocker_id, blocked_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders_sent (
                date_id INTEGER,
                reminder_year INTEGER,
                PRIMARY KEY (date_id, reminder_year)
            )
        ''')

        self.cursor.execute('''
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaks (
                user1_id INTEGER,
                user2_id INTEGER,
                streak_count INTEGER DEFAULT 0,
                last_streak_date TEXT,
                last_send_user1 TEXT,
                last_send_user2 TEXT,
                PRIMARY KEY (user1_id, user2_id)
            )
        ''')

        self.commit()

        self.cursor.execute("PRAGMA table_info(users)")
        existing_columns = [column[1] for column in self.cursor.fetchall()]

        if 'username' not in existing_columns:
            self.cursor.execute('ALTER TABLE users ADD COLUMN username TEXT')
            print("🔧 База данных обновлена: добавлена колонка 'username'")
            
        if 'timeout_until' not in existing_columns:
            self.cursor.execute('ALTER TABLE users ADD COLUMN timeout_until TEXT')
            print("🔧 База данных обновлена: добавлена колонка 'timeout_until'")
            
        self.commit()

    def add_or_update_user(self, user_id: int, gender: str, username: str):
        """
        @brief Добавляет нового пользователя или обновляет существующего (upsert).
        @param user_id ID пользователя.
        @param gender Пол пользователя ('male' или 'female').
        @param username Telegram-никнейм.
        """
        clean_username = username.replace('@', '') if username else None
        
        self.cursor.execute('''
            INSERT INTO users (user_id, username, gender) 
            VALUES (?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET 
                gender=excluded.gender, 
                username=excluded.username
        ''', (user_id, clean_username, gender))
        self.commit()

    def get_id_by_username(self, username: str):
        """
        @brief Ищет ID пользователя по его Telegram-никнейму.
        @param username Никнейм пользователя.
        @return ID пользователя или None.
        """
        clean_username = username.replace('@', '')
        self.cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def link_partners(self, user_id: int, partner_id: int):
        """
        @brief Устанавливает двустороннюю связь между партнерами.
        @param user_id ID первого пользователя.
        @param partner_id ID второго пользователя.
        """
        self.cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (partner_id, user_id))
        self.cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (user_id, partner_id))
        self.commit()

    def get_gender(self, user_id: int):
        """
        @brief Получает пол пользователя.
        @param user_id ID пользователя.
        @return Строка с полом ('male'/'female') или None.
        """
        self.cursor.execute('SELECT gender FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_partner(self, user_id: int):
        """
        @brief Получает ID партнера для указанного пользователя.
        @param user_id ID пользователя.
        @return ID партнера или None.
        """
        self.cursor.execute('SELECT partner_id FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def unlink_partners(self, user_id: int):
        """
        @brief Разрывает связь между партнерами.
        @param user_id ID инициатора разрыва.
        @return ID бывшего партнера или None.
        """
        partner_id = self.get_partner(user_id)
        if partner_id:
            self.cursor.execute('UPDATE users SET partner_id = NULL WHERE user_id = ?', (user_id,))
            self.cursor.execute('UPDATE users SET partner_id = NULL WHERE user_id = ?', (partner_id,))
            self.commit()
            return partner_id
        return None

    def get_all_users(self):
        """
        @brief Возвращает список всех ID пользователей из БД.
        @return Список целых чисел (ID пользователей).
        """
        self.cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in self.cursor.fetchall()]

    def get_stats(self):
        """
        @brief Возвращает статистику использования бота.
        @return Кортеж (всего_пользователей, всего_взаимных_пар).
        """
        self.cursor.execute('SELECT COUNT(*) FROM users')
        total_users = self.cursor.fetchone()[0]
        
        self.cursor.execute('''
            SELECT COUNT(*) 
            FROM users u1
            JOIN users u2 ON u1.partner_id = u2.user_id
            WHERE u2.partner_id = u1.user_id AND u1.user_id < u2.user_id
        ''')
        total_pairs = self.cursor.fetchone()[0]
        
        return total_users, total_pairs

    # ==========================================
    # ФУНКЦИИ ДЛЯ ЧЕРНОГО СПИСКА
    # ==========================================

    def block_user(self, blocker_id: int, blocked_id: int):
        """
        @brief Добавляет пользователя в черный список.
        """
        self.cursor.execute('INSERT OR IGNORE INTO blocked_users (blocker_id, blocked_id) VALUES (?, ?)', (blocker_id, blocked_id))
        self.commit()

    def unblock_user(self, blocker_id: int, blocked_id: int):
        """
        @brief Удаляет пользователя из черного списка.
        """
        self.cursor.execute('DELETE FROM blocked_users WHERE blocker_id = ? AND blocked_id = ?', (blocker_id, blocked_id))
        self.commit()

    def is_blocked(self, blocker_id: int, blocked_id: int):
        """
        @brief Проверяет факт блокировки.
        @return True, если blocked_id заблокирован blocker_id.
        """
        self.cursor.execute('SELECT 1 FROM blocked_users WHERE blocker_id = ? AND blocked_id = ?', (blocker_id, blocked_id))
        return self.cursor.fetchone() is not None

    def get_blocked_users(self, blocker_id: int):
        """
        @brief Возвращает список заблокированных пользователей.
        @return Список кортежей (ID, username).
        """
        self.cursor.execute('''
            SELECT b.blocked_id, u.username
            FROM blocked_users b
            LEFT JOIN users u ON b.blocked_id = u.user_id
            WHERE b.blocker_id = ?
        ''', (blocker_id,))
        return self.cursor.fetchall()

    def get_username(self, user_id: int):
        """
        @brief Получает никнейм по ID.
        @return Никнейм (без @) или None.
        """
        self.cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result and result[0] else None

    # ==========================================
    # ФУНКЦИИ ДЛЯ ВАЖНЫХ ДАТ
    # ==========================================

    def add_important_date(self, user_id: int, partner_id: int, title: str, event_date: str, is_annual: int, remind_days_before: int):
        """
        @brief Добавляет общую важную дату для пары.
        """
        self.cursor.execute('''
            INSERT INTO important_dates (user1_id, user2_id, title, event_date, is_annual, remind_days_before)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, partner_id, title, event_date, is_annual, remind_days_before))
        self.commit()
        return self.cursor.lastrowid

    def get_dates_for_user(self, user_id: int):
        """
        @brief Возвращает все важные даты пользователя, включая создателя.
        @return Список кортежей с данными дат.
        """
        self.cursor.execute('''
            SELECT d.id, d.title, d.event_date, d.is_annual, d.remind_days_before, d.user1_id, u.username
            FROM important_dates d
            LEFT JOIN users u ON d.user1_id = u.user_id
            WHERE d.user1_id = ? OR d.user2_id = ?
            ORDER BY d.event_date DESC
        ''', (user_id, user_id))
        return self.cursor.fetchall()

    def delete_date(self, date_id: int, user_id: int):
        """
        @brief Удаляет важную дату (с проверкой прав).
        @return True если удалено, иначе False.
        """
        self.cursor.execute('''
            DELETE FROM important_dates 
            WHERE id = ? AND (user1_id = ? OR user2_id = ?)
        ''', (date_id, user_id, user_id))
        self.commit()
        return self.cursor.rowcount > 0 

    def get_dates_to_remind(self, today_date: str):
        """
        @brief Ищет даты, о которых нужно напомнить сегодня.
        """
        self.cursor.execute('''
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
        return self.cursor.fetchall()

    def was_reminder_sent(self, date_id: int, year: int):
        """
        @brief Проверяет статус отправки напоминания в заданном году.
        """
        self.cursor.execute('SELECT 1 FROM reminders_sent WHERE date_id = ? AND reminder_year = ?', (date_id, year))
        return self.cursor.fetchone() is not None

    def mark_reminder_sent(self, date_id: int, year: int):
        """
        @brief Фиксирует факт отправки напоминания.
        """
        self.cursor.execute('INSERT OR IGNORE INTO reminders_sent VALUES (?, ?)', (date_id, year))
        self.commit()

    # ==========================================
    # ФУНКЦИИ ДЛЯ ОБЩЕГО ВИШЛИСТА И СЕРИЙ
    # ==========================================

    def add_wish(self, user1_id: int, user2_id: int, creator_id: int, wish_type: str, title: str, description: str):
        """
        @brief Добавляет элемент в вишлист пары.
        """
        self.cursor.execute('''
            INSERT INTO wishlist
            (user1_id, user2_id, creator_id, wish_type, title, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user1_id, user2_id, creator_id, wish_type, title, description))
        self.commit()
        return self.cursor.lastrowid

    def get_wishlist(self, user_id: int):
        """
        @brief Получает вишлист пары для указанного пользователя.
        """
        self.cursor.execute('''
            SELECT w.id, w.wish_type, w.title, w.description,
                   w.creator_id, u.username
            FROM wishlist w
            LEFT JOIN users u ON w.creator_id = u.user_id
            WHERE w.user1_id = ? OR w.user2_id = ?
            ORDER BY w.created_at DESC
        ''', (user_id, user_id))
        return self.cursor.fetchall()

    def delete_wish(self, wish_id: int, user_id: int):
        """
        @brief Удаляет элемент вишлиста (с проверкой прав).
        """
        self.cursor.execute('''
            DELETE FROM wishlist
            WHERE id = ?
            AND (user1_id = ? OR user2_id = ?)
        ''', (wish_id, user_id, user_id))
        self.commit()
        return self.cursor.rowcount > 0

    def update_streak(self, user_id: int, partner_id: int):
        """
        @brief Обновляет счетчик подряд идущих дней общения (streak).
        """
        today = datetime.now().strftime("%Y-%m-%d")
        u1, u2 = (user_id, partner_id) if user_id < partner_id else (partner_id, user_id)

        self.cursor.execute('''
            SELECT streak_count, last_streak_date, last_send_user1, last_send_user2
            FROM streaks WHERE user1_id = ? AND user2_id = ?
        ''', (u1, u2))
        row = self.cursor.fetchone()

        if row is None:
            streak_count, last_streak_date, last_send_u1, last_send_u2 = 0, None, None, None
        else:
            streak_count, last_streak_date, last_send_u1, last_send_u2 = row

        if user_id == u1:
            last_send_u1 = today
        else:
            last_send_u2 = today

        both_sent_today = (last_send_u1 == today and last_send_u2 == today)
        new_streak = streak_count
        new_last_streak_date = last_streak_date

        if both_sent_today:
            if last_streak_date is None:
                new_streak = 1
                new_last_streak_date = today
            elif last_streak_date != today:
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                if last_streak_date == yesterday:
                    new_streak = streak_count + 1
                else:
                    new_streak = 1
                new_last_streak_date = today

        self.cursor.execute('''
            INSERT OR REPLACE INTO streaks
            (user1_id, user2_id, streak_count, last_streak_date, last_send_user1, last_send_user2)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (u1, u2, new_streak, new_last_streak_date, last_send_u1, last_send_u2))
        self.commit()

    def get_streak(self, user_id: int, partner_id: int):
        """
        @brief Возвращает текущее значение серии для пары.
        """
        u1, u2 = (user_id, partner_id) if user_id < partner_id else (partner_id, user_id)
        self.cursor.execute('SELECT streak_count FROM streaks WHERE user1_id = ? AND user2_id = ?', (u1, u2))
        row = self.cursor.fetchone()
        return row[0] if row else 0

    def get_wish_by_id(self, wish_id: int):
        """
        @brief Получает данные конкретного желания по ID.
        """
        self.cursor.execute('SELECT id, wish_type, title, description, creator_id FROM wishlist WHERE id = ?', (wish_id,))
        return self.cursor.fetchone()

    def get_date_by_id(self, date_id: int):
        """
        @brief Получает данные конкретной важной даты по ID.
        """
        self.cursor.execute('SELECT id, title, event_date, is_annual, remind_days_before FROM important_dates WHERE id = ?', (date_id,))
        return self.cursor.fetchone()

    def is_wish_owner(self, user_id: int, wish_id: int):
        """
        @brief Проверяет наличие прав пользователя на желание.
        """
        self.cursor.execute('SELECT 1 FROM wishlist WHERE id = ? AND (user1_id = ? OR user2_id = ?)', (wish_id, user_id, user_id))
        return self.cursor.fetchone() is not None

    def is_date_owner(self, user_id: int, date_id: int):
        """
        @brief Проверяет наличие прав пользователя на дату.
        """
        self.cursor.execute('SELECT 1 FROM important_dates WHERE id = ? AND (user1_id = ? OR user2_id = ?)', (date_id, user_id, user_id))
        return self.cursor.fetchone() is not None

    # ==========================================
    # ФУНКЦИИ ДЛЯ МУД-ТРЕКЕРА
    # ==========================================

    def set_mood(self, user_id: int, mood: str):
        """
        @brief Добавляет новую запись о настроении пользователя.
        """
        self.cursor.execute('''
            INSERT INTO moods (user_id, mood)
            VALUES (?, ?)
        ''', (user_id, mood))
        self.commit()

    def get_latest_mood(self, user_id: int):
        """
        @brief Возвращает последнее установленное настроение пользователя.
        """
        self.cursor.execute('''
            SELECT mood, created_at 
            FROM moods 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (user_id,))
        return self.cursor.fetchone()

    def get_mood_stats(self, user_id: int):
        """
        @brief Возвращает статистику настроений пользователя.
        @return Словарь {настроение: количество}.
        """
        self.cursor.execute('''
            SELECT mood, COUNT(*) 
            FROM moods 
            WHERE user_id = ? 
            GROUP BY mood
        ''', (user_id,))
        return dict(self.cursor.fetchall())

    def get_mood_history(self, user1_id: int, user2_id: int, limit: int = 15):
        """
        @brief Возвращает историю настроений для пары.
        """
        self.cursor.execute('''
            SELECT m.user_id, m.mood, m.created_at, u.username
            FROM moods m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.user_id IN (?, ?)
            ORDER BY m.created_at DESC
            LIMIT ?
        ''', (user1_id, user2_id, limit))
        return self.cursor.fetchall()

    # ==========================================
    # ФУНКЦИИ ДЛЯ «УГЛА» (ТАЙМАУТА)
    # ==========================================

    def set_timeout(self, user_id: int, minutes: int):
        """
        @brief Отправляет пользователя в угол на заданное время.
        """
        timeout_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('UPDATE users SET timeout_until = ? WHERE user_id = ?', (timeout_time, user_id))
        self.commit()

    def get_timeout(self, user_id: int):
        """
        @brief Проверяет, находится ли пользователь в таймауте.
        @return Объект datetime или None.
        """
        self.cursor.execute('SELECT timeout_until FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        
        if result and result[0]:
            timeout_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < timeout_time:
                return timeout_time
            else:
                self.clear_timeout(user_id)
                
        return None

    def clear_timeout(self, user_id: int):
        """
        @brief Досрочно снимает таймаут с пользователя.
        """
        self.cursor.execute('UPDATE users SET timeout_until = NULL WHERE user_id = ?', (user_id,))
        self.commit()

# Инициализируем глобальный объект для обратной совместимости с main.py
bot_db = BotDatabase()