import sqlite3

conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    """Создает таблицу или обновляет её структуру, сохраняя старые данные"""
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            partner_id INTEGER
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
    clean_username = username.replace('@', '') if username else None
    
    cursor.execute('''
        INSERT INTO users (user_id, username, gender) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET 
            gender=excluded.gender, 
            username=excluded.username
    ''', (user_id, clean_username, gender))
    conn.commit()

def get_id_by_username(username):
    """Ищет числовой ID по никнейму"""
    clean_username = username.replace('@', '')
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
    result = cursor.fetchone()
    return result[0] if result else None

def link_partners(user_id, partner_id):
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (partner_id, user_id))
    cursor.execute('UPDATE users SET partner_id = ? WHERE user_id = ?', (user_id, partner_id))
    conn.commit()

def get_gender(user_id):
    cursor.execute('SELECT gender FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_partner(user_id):
    cursor.execute('SELECT partner_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None