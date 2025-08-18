import sqlite3


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('support.db')
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        full_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Таблица сообщений
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        message_text TEXT,
                        is_admin BOOLEAN DEFAULT 0,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')

    conn.commit()
    conn.close()


# Вызов при старте
init_db()
