import sqlite3


conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

# Инициализация базы данных (создание таблицы, если ее нет)
def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            partner_id INTEGER
        )
    ''')
    conn.commit()

# Функция для добавления нового пользователя или обновления его пола
def add_or_update_user(user_id, gender):
    cursor.execute('''
        INSERT INTO users (user_id, gender) 
        VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET gender=excluded.gender
    ''', (user_id, gender))
    conn.commit()

# Функция для получения информации о пользователе
def link_partners(user_id, partner_id):
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (partner_id, user_id))
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (user_id, partner_id))
    conn.commit()

# Функция для получения пола пользователя
def get_gender(user_id):
    cursor.execute('SELECT gender FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0] 
    return None

# Функция для получения ID партнера пользователя
def get_partner(user_id):
    cursor.execute('SELECT partner_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None