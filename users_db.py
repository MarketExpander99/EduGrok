import logging
import sqlite3
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

def init_users_tables(conn):
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col for col in c.fetchall()}
        if not columns:
            logger.debug("Creating users table")
            c.execute('''CREATE TABLE users 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                          grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT, 
                          language TEXT DEFAULT 'en', star_coins INTEGER DEFAULT 0)''')
        else:
            missing_cols = [col for col in ['grade', 'theme', 'subscribed', 'handle', 'language', 'star_coins'] 
                            if col not in columns]
            if missing_cols:
                logger.debug(f"Migrating users table: {missing_cols}")
                c.execute("DROP TABLE IF EXISTS users_new")
                c.execute('''CREATE TABLE users_new 
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                              grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT, 
                              language TEXT DEFAULT 'en', star_coins INTEGER DEFAULT 0)''')
                c.execute('''INSERT INTO users_new SELECT * FROM users''')
                c.execute('DROP TABLE users')
                c.execute('ALTER TABLE users_new RENAME TO users')
                conn.commit()
                logger.info("Migrated users table")
                print("Migrated users table")
        
        c.execute('''CREATE TABLE IF NOT EXISTS feedback 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating INTEGER, comments TEXT, submitted_date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS games 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game_type TEXT, score INTEGER, played_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
    except sqlite3.Error as e:
        logger.error(f"Error initializing users tables: {e}")
        conn.rollback()
        raise

def seed_users(conn):
    c = conn.cursor()
    try:
        bots = [
            ('skykidz@example.com', generate_password_hash('botpass'), 1, 'farm', 0, 'SkyKidz', 'en', 0),
            ('grokedu@example.com', generate_password_hash('botpass'), 2, 'space', 0, 'GrokEdu', 'en', 0),
        ]
        c.executemany("INSERT OR IGNORE INTO users (email, password, grade, theme, subscribed, handle, language, star_coins) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", bots)
        
        c.execute("SELECT id FROM users WHERE email = 'skykidz@example.com'")
        skykidz_row = c.fetchone()
        skykidz_id = skykidz_row[0] if skykidz_row else None
        c.execute("SELECT id FROM users WHERE email = 'grokedu@example.com'")
        grokedu_row = c.fetchone()
        grokedu_id = grokedu_row[0] if grokedu_row else None
        
        return skykidz_id, grokedu_id
    except sqlite3.Error as e:
        logger.error(f"Error seeding users: {e}")
        raise

def check_users_schema(conn):
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        expected = {
            'id': 'INTEGER', 'email': 'TEXT', 'password': 'TEXT',
            'grade': 'INTEGER', 'theme': 'TEXT', 'subscribed': 'INTEGER',
            'handle': 'TEXT', 'language': 'TEXT', 'star_coins': 'INTEGER'
        }
        for col, col_type in expected.items():
            if col not in columns:
                if col == 'star_coins':
                    c.execute("ALTER TABLE users ADD COLUMN star_coins INTEGER DEFAULT 0")
                    conn.commit()
                    logger.info("Added star_coins column to users table")
                    print("Added star_coins column to users table")
                else:
                    logger.error(f"Users table missing column: {col}")
                    raise ValueError(f"Users table missing column: {col}")
            elif columns[col] != col_type.split()[0]:
                logger.error(f"Users table column {col} type mismatch: expected {col_type}, got {columns[col]}")
                raise ValueError(f"Users table column {col} type mismatch")
        
        for table in ['feedback', 'games']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                logger.error(f"Table {table} missing")
                raise ValueError(f"Table {table} missing")
    except Exception as e:
        logger.error(f"Users schema check failed: {str(e)}")
        raise