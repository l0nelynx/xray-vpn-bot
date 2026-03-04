"""
Support Bot Database Module
Works with the main application database (db.sqlite3)
"""
import sqlite3
from pathlib import Path
from datetime import datetime


DB_PATH = Path('db/db.sqlite3')


def get_db_connection():
    """Get connection to the main database"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_support_tables():
    """Initialize support-related tables in the main database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Support users table (stores support ticket info)
    cursor.execute('''CREATE TABLE IF NOT EXISTS support_users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        full_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Support messages table
    cursor.execute('''CREATE TABLE IF NOT EXISTS support_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        message_text TEXT,
                        is_admin BOOLEAN DEFAULT 0,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES support_users(user_id))''')

    conn.commit()
    conn.close()


def add_support_user(user_id: int, username: str, full_name: str):
    """Add or update support user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT OR IGNORE INTO support_users (user_id, username, full_name) 
                      VALUES (?, ?, ?)""",
                   (user_id, username, full_name))
    conn.commit()
    conn.close()


def add_support_message(user_id: int, message_text: str, is_admin: bool = False):
    """Add message to support conversation"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO support_messages (user_id, message_text, is_admin) 
                      VALUES (?, ?, ?)""",
                   (user_id, message_text, is_admin))
    conn.commit()
    conn.close()


def get_support_user(user_id: int):
    """Get support user info"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, full_name FROM support_users WHERE user_id = ?",
                   (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result


def get_user_messages(user_id: int, limit: int = 10):
    """Get recent messages for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT message_text, is_admin, timestamp FROM support_messages 
                      WHERE user_id = ? 
                      ORDER BY timestamp DESC 
                      LIMIT ?""",
                   (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results
"""
Support Bot Configuration Module
Isolated from main app, loads settings from config.yml
"""
from pathlib import Path
import yaml


def load_config(file_path="config.yml"):
    """Load configuration from YAML file"""
    config_path = Path(file_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML: {exc}")


# Load configuration when module is imported
try:
    config = load_config()
except Exception as e:
    print(f"⚠️ Error loading config: {e}")
    config = {}


def get(key, default=None):
    """Get config value by key"""
    return config.get(key, default)


# Common config values for support bot
SUPPORT_TOKEN = get('support_token')
ADMIN_ID = get('admin_id')
DB_PATH = Path('db/db.sqlite3')

