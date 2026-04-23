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
    Создает таблицу users, если её еще нет, и безопасно добавляет
    новые колонки (например, username) для старых пользователей.
    """
    # 1. Создаем базовую структуру таблицы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            partner_id INTEGER
        )
    ''')
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
    """Возвращает статистику: (всего пользователей, количество образованных пар)"""
    # Считаем абсолютно всех зарегистрированных юзеров
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # Считаем тех, у кого заполнено поле partner_id (кто состоит в паре)
    cursor.execute('SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL')
    paired_users = cursor.fetchone()[0]
    
    # Так как в паре два человека, делим количество на 2
    total_pairs = paired_users // 2
    
    return total_users, total_pairs