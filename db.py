import sqlite3

# ==========================================
# НАСТРОЙКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ
# ==========================================
# check_same_thread=False необходим для многопоточных приложений (каким является telebot),
# чтобы разные потоки могли безопасно обращаться к одному файлу базы данных.
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()


def init_db():
    """Инициализация базы данных: создание таблиц, если они не существуют."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gender TEXT,
            partner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Новая таблица для статистики сообщений между парами
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_stats (
            user1_id INTEGER,
            user2_id INTEGER,
            message_count INTEGER DEFAULT 0,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user1_id, user2_id)
        )
    ''')

    # Если нужно, можно добавить и другие таблицы (например, drafts)
    # cursor.execute('''CREATE TABLE IF NOT EXISTS drafts ...''')

    conn.commit()

    # 2. Получаем информацию о текущих колонках в таблице (используем системную команду PRAGMA)
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    # 3. Механизм "миграции": если колонки username нет в старой базе, добавляем её.
    # Это спасает базу от поломки при выкате обновлений для бота.
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

def get_username(user_id):
    """Возвращает username пользователя по его ID."""
    cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
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

# ------> Статистика
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

def increment_message_count(user_id, partner_id):
    """Увеличивает счётчик сообщений между двумя партнёрами."""
    # Определяем пару в каноническом порядке (меньший ID — первый)
    user1, user2 = sorted([user_id, partner_id])
    # Пытаемся увеличить существующий счётчик
    cursor.execute('''
        UPDATE messages_stats
        SET message_count = message_count + 1, last_message_at = CURRENT_TIMESTAMP
        WHERE user1_id = ? AND user2_id = ?
    ''', (user1, user2))

    if cursor.rowcount == 0:
        # Если записи не было — создаём новую со счётчиком 1
        cursor.execute('''
            INSERT INTO messages_stats (user1_id, user2_id, message_count, last_message_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ''', (user1, user2))

    conn.commit()

def get_partner_stats(user_id):
    """Возвращает статистику для пары пользователя: ID, общий счётчик, ID партнёра."""
    partner_id = get_partner(user_id)
    if not partner_id:
        return None

    user1, user2 = sorted([user_id, partner_id])

    cursor.execute('''
        SELECT message_count
        FROM messages_stats
        WHERE user1_id = ? AND user2_id = ?
    ''', (user1, user2))

    result = cursor.fetchone()
    message_count = result[0] if result else 0

    return user_id, message_count, partner_id