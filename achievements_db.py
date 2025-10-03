import logging
import sqlite3

logger = logging.getLogger(__name__)

def init_achievements_tables(c):
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS user_points 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, points INTEGER, earned_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS badges 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, badge_name TEXT, awarded_date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        # FIXED: Added missing tables for games, tests, feedback
        c.execute('''CREATE TABLE IF NOT EXISTS games 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, score INTEGER, played_at TEXT DEFAULT (datetime('now')),
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS tests 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, score INTEGER, date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS feedback 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating INTEGER, comments TEXT, submitted_date TEXT DEFAULT (datetime('now')),
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
    except sqlite3.Error as e:
        logger.error(f"Error initializing achievements tables: {e}")
        raise

def check_achievements_schema(conn):
    c = conn.cursor()
    try:
        # Check badges table for awarded_date (migrate from earned_at if exists)
        c.execute("PRAGMA table_info(badges)")
        columns_list = c.fetchall()
        if not columns_list:
            logger.error("Table badges missing")
            raise ValueError("Table badges missing")
        columns = {col[1]: col[2] for col in columns_list}
        if 'earned_at' in columns and 'awarded_date' not in columns:
            # Migrate earned_at to awarded_date
            c.execute("ALTER TABLE badges RENAME COLUMN earned_at TO awarded_date")
            conn.commit()
            logger.info("Renamed earned_at to awarded_date in badges table")
            print("Renamed earned_at to awarded_date in badges table")
        elif 'awarded_date' not in columns:
            c.execute("ALTER TABLE badges ADD COLUMN awarded_date TEXT")
            conn.commit()
            logger.info("Added awarded_date column to badges table")
            print("Added awarded_date column to badges table")
        
        for table in ['user_points', 'badges', 'games', 'tests', 'feedback']:  # FIXED: Include new tables
            try:
                c.execute(f"PRAGMA table_info({table})")
                if not c.fetchall():
                    logger.error(f"Table {table} missing")
                    raise ValueError(f"Table {table} missing")
            except sqlite3.OperationalError:
                logger.error(f"Table {table} does not exist")
                raise ValueError(f"Table {table} missing")
    except Exception as e:
        logger.error(f"Achievements schema check failed: {str(e)}")
        raise