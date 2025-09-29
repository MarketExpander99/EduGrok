import logging
import sqlite3
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

def init_users_tables(conn):
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            grade INTEGER NOT NULL,
            theme TEXT DEFAULT 'astronaut',
            subscribed INTEGER DEFAULT 0,
            handle TEXT,
            language TEXT DEFAULT 'en',
            star_coins INTEGER DEFAULT 0
        )''')
        conn.commit()
        logger.info("Users table initialized")
        print("Users table initialized")
    except sqlite3.Error as e:
        logger.error(f"Error creating users table: {e}")
        conn.rollback()
        raise

def seed_users(conn):
    c = conn.cursor()
    try:
        # Bot users (passwords hashed)
        hashed_bot = generate_password_hash('botpass', method='pbkdf2:sha256')
        c.execute("INSERT OR IGNORE INTO users (email, password, grade, handle, theme, language, star_coins) VALUES (?, ?, ?, ?, ?, ?, 0)",
                  ('skykidz@grok.com', hashed_bot, 2, 'SkyKidz', 'astronaut', 'en'))
        skykidz_id = c.lastrowid if c.lastrowid else c.execute("SELECT id FROM users WHERE email=?", ('skykidz@grok.com',)).fetchone()[0]
        
        c.execute("INSERT OR IGNORE INTO users (email, password, grade, handle, theme, language, star_coins) VALUES (?, ?, ?, ?, ?, ?, 0)",
                  ('grokedu@grok.com', hashed_bot, 3, 'GrokEdu', 'farm', 'bilingual'))
        grokedu_id = c.lastrowid if c.lastrowid else c.execute("SELECT id FROM users WHERE email=?", ('grokedu@grok.com',)).fetchone()[0]
        
        conn.commit()
        logger.info(f"Seeded users: SkyKidz {skykidz_id}, GrokEdu {grokedu_id}")
        print(f"Seeded users: SkyKidz {skykidz_id}, GrokEdu {grokedu_id}")
        return skykidz_id, grokedu_id
    except Exception as e:
        logger.error(f"Seed users failed: {e}")
        conn.rollback()
        raise

def check_users_schema(conn):
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        if 'star_coins' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN star_coins INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added star_coins to users table")
            print("Added star_coins to users table")
        # Add more migrations as needed (e.g., handle if missing)
        if 'handle' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN handle TEXT")
            conn.commit()
            logger.info("Added handle to users table")
        logger.debug("Users schema check passed")
    except Exception as e:
        logger.error(f"Users schema check failed: {str(e)}")
        raise