import sqlite3

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
            partner_id INTEGER
        )
    ''')
    
    #Таблица для черного списка
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            blocker_id INTEGER,
            blocked_id INTEGER,
            PRIMARY KEY (blocker_id, blocked_id)
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