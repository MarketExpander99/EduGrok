import os
import sqlite3
import logging
from werkzeug.security import generate_password_hash
from flask import g

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='/tmp/db.log', level=logging.DEBUG)

# DB connection
def get_db():
    if 'db' not in g:
        default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'edugrok.db')
        if 'RENDER' in os.environ:
            db_path = '/data/edugrok.db'
            logger.debug(f"Using Render DB path: {db_path}")
            print(f"Using Render DB path: {db_path}")
        else:
            db_path = os.environ.get('DB_PATH', default_db_path)
            logger.debug(f"Using DB path: {db_path} (default: {default_db_path})")
            print(f"Using DB path: {db_path} (default: {default_db_path})")
        
        db_dir = os.path.dirname(db_path)
        if db_dir and db_dir != os.path.dirname(os.path.abspath(__file__)) and not os.path.exists(db_dir):
            try:
                parent_dir = os.path.dirname(db_dir)
                if parent_dir and not os.access(parent_dir, os.W_OK):
                    logger.error(f"Parent directory not writable: {parent_dir}")
                    print(f"Parent directory not writable: {parent_dir}")
                    raise PermissionError(f"Cannot write to {parent_dir}")
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created DB directory: {db_dir}")
                print(f"Created DB directory: {db_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating {db_dir}: {str(e)}")
                print(f"Permission denied creating {db_dir}: {e}")
                raise
        
        if not os.path.exists(db_path):
            logger.info(f"DB not found at {db_path} - creating")
            print(f"DB not found at {db_path} - creating")
            try:
                if not os.access(os.path.dirname(db_path), os.W_OK):
                    logger.error(f"Directory not writable: {os.path.dirname(db_path)}")
                    print(f"Directory not writable: {os.path.dirname(db_path)}")
                    raise PermissionError(f"Cannot write to {os.path.dirname(db_path)}")
                with open(db_path, 'a'):
                    pass
                logger.info(f"Created DB at {db_path}")
                print(f"Created DB at {db_path}")
            except PermissionError as e:
                logger.error(f"Permission denied at {db_path}: {str(e)}")
                print(f"Permission denied at {db_path}: {e}")
                raise
        
        try:
            g.db = sqlite3.connect(db_path, timeout=10)
            g.db.execute('PRAGMA journal_mode=WAL;')
            g.db.row_factory = sqlite3.Row
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to connect to DB at {db_path}: {str(e)}")
            print(f"Failed to connect to DB at {db_path}: {e}")
            raise
    return g.db

def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        logger.debug("Database connection closed")

# DB reset
def reset_db():
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS feedback")
        c.execute("DROP TABLE IF EXISTS badges")
        c.execute("DROP TABLE IF EXISTS user_points")
        c.execute("DROP TABLE IF EXISTS user_likes")
        c.execute("DROP TABLE IF EXISTS post_likes")
        c.execute("DROP TABLE IF EXISTS reposts")
        c.execute("DROP TABLE IF EXISTS comments")
        c.execute("DROP TABLE IF EXISTS games")
        c.execute("DROP TABLE IF EXISTS tests")
        c.execute("DROP TABLE IF EXISTS lesson_responses")
        c.execute("DROP TABLE IF EXISTS lessons")
        c.execute("DROP TABLE IF EXISTS posts")
        c.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        logger.info("Force reset: Dropped all tables")
        print("Dropped all tables")
        init_db()
        seed_lessons()
        check_db_schema()
        logger.info("Force reset complete")
        print("DB reset complete")
    except Exception as e:
        logger.error(f"DB reset failed: {str(e)}")
        print(f"DB reset failed: {e}")
        conn.rollback()
        raise

# Schema check
def check_db_schema():
    conn = get_db()
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
        
        # Check posts table for media_url, views, and reposts
        c.execute("PRAGMA table_info(posts)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'media_url' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN media_url TEXT")
            conn.commit()
            logger.info("Added media_url column to posts table")
            print("Added media_url column to posts table")
        if 'views' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added views column to posts table")
            print("Added views column to posts table")
        if 'reposts' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN reposts INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added reposts column to posts table")
            print("Added reposts column to posts table")
        
        for table in ['lessons', 'lesson_responses', 'tests', 'user_likes', 'post_likes', 'user_points', 'badges', 'feedback', 'games', 'reposts', 'comments']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                logger.error(f"Table {table} missing")
                raise ValueError(f"Table {table} missing")
        logger.debug("Schema check passed")
        print("Schema check passed")
    except Exception as e:
        logger.error(f"Schema check failed: {str(e)}")
        raise

# Initialize DB
def init_db():
    conn = get_db()
    c = conn.cursor()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchall()[0][2]
        logger.debug(f"Initializing DB at {db_path}")
        print(f"Initializing DB at {db_path}")
        
        # Drop and recreate posts table to ensure correct schema
        c.execute('''CREATE TABLE IF NOT EXISTS posts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, handle TEXT, content TEXT, 
                      subject TEXT, grade INTEGER, likes INTEGER DEFAULT 0, created_at TEXT, media_url TEXT, views INTEGER DEFAULT 0, reposts INTEGER DEFAULT 0,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Drop and recreate lessons table to ensure new columns are included
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, 
                      subject TEXT, content TEXT, completed BOOLEAN DEFAULT 0, 
                      trace_word TEXT, sound TEXT, spell_word TEXT, mc_question TEXT, 
                      mc_options TEXT, mc_answer TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Users table
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
                       ...(truncated 3415 characters)... users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS feedback 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating INTEGER, comments TEXT, submitted_date TEXT, 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS games 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, score INTEGER, 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS reposts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, post_id INTEGER, created_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (post_id) REFERENCES posts(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS comments 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER, content TEXT, created_at TEXT,
                      FOREIGN KEY (post_id) REFERENCES posts(id), 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_id ON posts(id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_user_grade_completed ON lessons(user_id, grade, completed)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tests_user_date ON tests(user_id, date)')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_unique ON posts(user_id, content)')
        conn.commit()
        logger.info("Tables created/updated")
        print("Tables created/updated")

        # Seed bot users
        bots = [
            ('skykidz@example.com', generate_password_hash('botpass'), 1, 'farm', 0, 'SkyKidz', 'en', 0),
            ('grokedu@example.com', generate_password_hash('botpass'), 2, 'space', 0, 'GrokEdu', 'en', 0),
        ]
        c.executemany("INSERT OR IGNORE INTO users (email, password, grade, theme, subscribed, handle, language, star_coins) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", bots)
        conn.commit()
        logger.info("Bot users inserted")
        print("Bot users inserted")

        # Fetch bot user IDs
        c.execute("SELECT id FROM users WHERE email = 'skykidz@example.com'")
        skykidz_row = c.fetchone()
        skykidz_id = skykidz_row[0] if skykidz_row else None
        c.execute("SELECT id FROM users WHERE email = 'grokedu@example.com'")
        grokedu_row = c.fetchone()
        grokedu_id = grokedu_row[0] if grokedu_row else None

        if skykidz_id is None or grokedu_id is None:
            logger.error("Failed to retrieve bot user IDs. SkyKidz ID: %s, GrokEdu ID: %s", skykidz_id, grokedu_id)
            c.execute("SELECT email, id FROM users")
            users = c.fetchall()
            logger.debug("Current users in DB: %s", [(row[0], row[1]) for row in users])
            raise ValueError(f"Bot user insertion failed. SkyKidz ID: {skykidz_id}, GrokEdu ID: {grokedu_id}")

        logger.debug("Bot user IDs: SkyKidz=%s, GrokEdu=%s", skykidz_id, grokedu_id)
        print(f"Bot user IDs: SkyKidz={skykidz_id}, GrokEdu={grokedu_id}")

        # Seed bot posts (updated to include views=0 and reposts=0)
        bot_posts = [
            (skykidz_id, 'SkyKidz', 'Check out this fun farm math adventure! 2 cows + 3 chickens = ?', 'math', 1, 5, 'datetime("now")', None, 0, 0),
            (grokedu_id, 'GrokEdu', 'Explore the solar system: Name a planet close to the sun.', 'science', 2, 10, 'datetime("now")', None, 0, 0),
        ]
        c.executemany("INSERT OR IGNORE INTO posts (user_id, handle, content, subject, grade, likes, created_at, media_url, views, reposts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", bot_posts)
        conn.commit()
        logger.info("Bot posts seeded")
        print("Bot posts seeded")

        # Fetch seeded post IDs
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%farm math%'", (skykidz_id,))
        row = c.fetchone()
        post1_id = row[0] if row else None
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%solar system%'", (grokedu_id,))
        row = c.fetchone()
        post2_id = row[0] if row else None
        if post1_id and post2_id:
            bot_comments = [
                (post1_id, skykidz_id, 'This is fun!', 'datetime("now")'),
                (post1_id, grokedu_id, 'Love the math adventure!', 'datetime("now")'),
                (post2_id, skykidz_id, 'Mercury?', 'datetime("now")'),
                (post2_id, grokedu_id, 'Great question!', 'datetime("now")'),
            ]
            c.executemany("INSERT OR IGNORE INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, ?)", bot_comments)
            conn.commit()
            logger.info("Bot comments seeded")
            print("Bot comments seeded")

    except sqlite3.Error as e:
        logger.error(f"SQLite error in init_db: {str(e)}")
        print(f"SQLite error in init_db: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"DB init failed: {str(e)}")
        print(f"DB init failed: {e}")
        conn.rollback()
        raise

# Seed lessons with media
def seed_lessons():
    conn = get_db()
    c = conn.cursor()
    lessons = [
        (None, 1, 'Phonics: Letter M', '<p>Learn the M sound with words like <strong>moon</strong> and <strong>mars</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Moon"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, 'moon', '/muːn/', 'moon', 'What is the correct spelling?', '["moon", "mon", "mooon", "mun"]', 'moon'),
        (None, 1, 'Math: Counting 1-10', '<p>Count from 1 to 10 with fun examples!</p><img src="https://via.placeholder.com/300x200" alt="Numbers">', 0, None, None, None, 'Count the numbers: How many apples? (Answer: 5)', '["3", "5", "7", "10"]', '5'),
        (None, 1, 'Science: Planets', '<p>Explore the planets in our solar system.</p><img src="https://via.placeholder.com/300x200" alt="Planets"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'Which planet is closest to the sun?', '["Earth", "Mars", "Mercury", "Jupiter"]', 'Mercury'),
        (None, 1, 'Math: Addition', '<p>Learn to add numbers up to 10.</p><img src="https://via.placeholder.com/300x200" alt="Addition">', 0, None, None, None, 'What is 4 + 3?', '["6", "7", "8", "5"]', '7'),
        (None, 1, 'Phonics: Letter S', '<p>Learn the S sound with words like <strong>sun</strong> and <strong>star</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Sun">', 0, 'sun', '/sʌn/', 'sun', 'What is the correct spelling?', '["sun", "son", "sunn", "sn"]', 'sun'),
        (None, 1, 'Science: Animals', '<p>Discover animals on Earth and beyond!</p><img src="https://via.placeholder.com/300x200" alt="Animals"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'Which animal says "meow"?', '["Dog", "Cat", "Bird", "Fish"]', 'Cat'),
        (None, 1, 'Phonics: Letter A', '<p>Learn the A sound with words like <strong>apple</strong> and <strong>ant</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Apple">', 0, 'apple', '/ˈæp.əl/', 'apple', 'What is the correct spelling?', '["apple", "aple", "appl", "aplle"]', 'apple'),
        (None, 2, 'Math: Shapes', '<p>Identify different shapes: Circle, Square, Triangle.</p><img src="https://via.placeholder.com/300x200" alt="Shapes">', 0, None, None, None, 'How many sides does a triangle have?', '["0", "3", "4", "Infinite"]', '3'),
        (None, 3, 'Science: Water Cycle', '<p>Learn about evaporation, condensation, and precipitation.</p><img src="https://via.placeholder.com/300x200" alt="Water Cycle"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'What is the first step in the water cycle?', '["Precipitation", "Evaporation", "Condensation", "Collection"]', 'Evaporation'),
        (None, 1, 'Language: Colors', '<p>Learn basic colors: Red, Blue, Green.</p><img src="https://via.placeholder.com/300x200" alt="Colors">', 0, 'red', '/rɛd/', 'red', 'What is the correct spelling?', '["red", "read", "rd", "redd"]', 'red'),
        (None, 2, 'Phonics: Letter B', '<p>Learn the B sound with words like <strong>book</strong> and <strong>ball</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Book">', 0, 'book', '/bʊk/', 'book', 'What is the correct spelling?', '["book", "buk", "boook", "bock"]', 'book'),
        (None, 3, 'Math: Fractions', '<p>Understand simple fractions like 1/2 and 1/4.</p><img src="https://via.placeholder.com/300x200" alt="Fractions">', 0, None, None, None, 'What is half of 8?', '["3", "4", "5", "6"]', '4'),
        (None, 2, 'math', '<p>Subtraction: Solve 10 - 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Subtraction">', 0, None, None, None, 'What is 7 - 2?', '["4", "5", "6", "3"]', '5'),
        (None, 3, 'math', '<p>Multiplication: Solve 3 x 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Multiplication">', 0, None, None, None, 'What is 5 x 3?', '["10", "15", "20", "12"]', '15'),
        (None, 2, 'science', '<p>Weather: What makes it rain?</p><img src="https://via.placeholder.com/300x200" alt="Weather"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'What is snow?', '["Frozen rain", "Hot wind", "Sunlight", "Clouds"]', 'Frozen rain')
    ]
    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lessons_unique ON lessons(grade, subject, content)')
        c.executemany("""
            INSERT OR IGNORE INTO lessons (user_id, grade, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, lessons)
        conn.commit()
        logger.debug("Seeded %d lessons", len(lessons))
        print(f"Seeded {len(lessons)} lessons")
    except sqlite3.OperationalError as e:
        logger.error(f"Seed lessons failed: {str(e)}")
        print(f"Seed lessons failed: {e}")
        conn.rollback()
        raise