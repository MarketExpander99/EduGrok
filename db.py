import os
import sqlite3
import logging
from werkzeug.security import generate_password_hash
from flask import g

# Configure logging
logger = logging.getLogger(__name__)

# DB connection
def get_db():
    if 'db' not in g:
        if 'RENDER' in os.environ:
            db_path = '/data/edugrok.db'
            print(f"Using Render DB path: {db_path}")
            logger.info(f"Using Render DB path: {db_path}")
            if not os.path.exists(db_path):
                print(f"DB not found at {db_path} - creating")
                try:
                    with open(db_path, 'a'):
                        pass
                    print(f"Created DB at {db_path}")
                    logger.info(f"Created DB at {db_path}")
                except PermissionError as e:
                    print(f"Permission denied at {db_path}: {e}")
                    logger.error(f"Permission denied at {db_path}: {e}")
                    raise
        else:
            db_path = 'edugrok.db'
            print(f"Using local DB path: {db_path}")
            logger.info(f"Using local DB path: {db_path}")
        g.db = sqlite3.connect(db_path, timeout=10)
        g.db.execute('PRAGMA journal_mode=WAL;')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# DB reset
def reset_db():
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS feedback")
        c.execute("DROP TABLE IF EXISTS badges")
        c.execute("DROP TABLE IF EXISTS user_points")
        c.execute("DROP TABLE IF EXISTS user_likes")
        c.execute("DROP TABLE IF EXISTS tests")
        c.execute("DROP TABLE IF EXISTS lessons")
        c.execute("DROP TABLE IF EXISTS posts")
        c.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        print("Dropped all tables")
        logger.info("Force reset: Dropped all tables")
        init_db()
        seed_lessons()
        check_db_schema()
        print("DB reset complete")
        logger.info("Force reset complete")
    except Exception as e:
        print(f"DB reset failed: {e}")
        logger.error(f"DB reset failed: {e}")
        conn.rollback()
        raise

# Schema check
def check_db_schema():
    conn = get_db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = {col[1]: col[2] for col in c.fetchall()}
    expected = {
        'id': 'INTEGER', 'email': 'TEXT', 'password': 'TEXT',
        'grade': 'INTEGER', 'theme': 'TEXT', 'subscribed': 'INTEGER DEFAULT 0',
        'handle': 'TEXT', 'language': 'TEXT'
    }
    for col, col_type in expected.items():
        if col not in columns:
            logger.error(f"Users table missing column: {col}")
            raise ValueError(f"Users table missing column: {col}")
        if columns[col] != col_type.split()[0]:
            logger.error(f"Users table column {col} type mismatch: expected {col_type}, got {columns[col]}")
            raise ValueError(f"Users table column {col} type mismatch")
    for table in ['posts', 'lessons', 'tests', 'user_likes', 'user_points', 'badges', 'feedback']:
        c.execute(f"PRAGMA table_info({table})")
        if not c.fetchall():
            logger.error(f"Table {table} missing")
            raise ValueError(f"Table {table} missing")
    logger.debug("Schema check passed")
    print("Schema check passed")

# Initialize DB
def init_db():
    conn = get_db()
    c = conn.cursor()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchall()[0][2]
        print(f"Initializing DB at {db_path}")
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col for col in c.fetchall()}
        if not columns:
            logger.debug("Creating users table")
            c.execute('''CREATE TABLE users 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                          grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT, language TEXT DEFAULT 'en')''')
        else:
            missing_cols = [col for col in ['grade', 'theme', 'subscribed', 'handle', 'language'] if col not in columns]
            if missing_cols:
                logger.debug(f"Migrating users table: {missing_cols}")
                c.execute("DROP TABLE IF EXISTS users_new")
                c.execute('''CREATE TABLE users_new 
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                              grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT, language TEXT DEFAULT 'en')''')
                old_cols = [col for col in columns if col != 'id']
                insert_cols = old_cols + missing_cols
                insert_cols_str = ', '.join(insert_cols)
                select_cols = ', '.join([col if col in old_cols else 'NULL' if col == 'grade' else "'astronaut'" if col == 'theme' else '0' if col == 'subscribed' else "email" if col == 'handle' else "'en'" for col in insert_cols])
                c.execute(f"INSERT INTO users_new (id, {insert_cols_str}) SELECT id, {select_cols} FROM users")
                c.execute("SELECT id, password FROM users_new WHERE password NOT LIKE 'pbkdf2:sha256%'")
                for row in c.fetchall():
                    user_id, plaintext = row[0], row[1]
                    hashed = generate_password_hash(plaintext)
                    c.execute("UPDATE users_new SET password = ? WHERE id = ?", (hashed, user_id))
                c.execute('DROP TABLE users')
                c.execute('ALTER TABLE users_new RENAME TO users')
                logger.debug("Migration completed")
                print("Users table migrated")
        c.execute('''CREATE TABLE IF NOT EXISTS posts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, subject TEXT, 
                      likes INTEGER DEFAULT 0, reported INTEGER DEFAULT 0, 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, 
                      subject TEXT, content TEXT, completed INTEGER DEFAULT 0, 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS tests 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, 
                      score INTEGER, date TEXT, 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_likes 
                     (user_id INTEGER, post_id INTEGER, 
                      PRIMARY KEY (user_id, post_id), 
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (post_id) REFERENCES posts(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_points 
                     (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS badges 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, badge_name TEXT, awarded_date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS feedback 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating INTEGER, comments TEXT, submitted_date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_reported_id ON posts(reported, id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_user_grade_completed ON lessons(user_id, grade, completed)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tests_user_date ON tests(user_id, date)')
        conn.commit()
        print("Tables created/updated")

        # Seed bot users
        bots = [
            ('skykidz@example.com', generate_password_hash('botpass'), 1, 'farm', 0, 'SkyKidz', 'en'),
            ('grokedu@example.com', generate_password_hash('botpass'), 2, 'space', 0, 'GrokEdu', 'en'),
        ]
        c.executemany("INSERT OR IGNORE INTO users (email, password, grade, theme, subscribed, handle, language) VALUES (?, ?, ?, ?, ?, ?, ?)", bots)
        conn.commit()
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

        print(f"Bot user IDs: SkyKidz={skykidz_id}, GrokEdu={grokedu_id}")
        logger.debug("Bot user IDs: SkyKidz=%s, GrokEdu=%s", skykidz_id, grokedu_id)

        # Seed bot posts
        bot_posts = [
            (skykidz_id, 'Check out this fun farm math adventure! 2 cows + 3 chickens = ?', 'math', 5, 0),
            (grokedu_id, 'Explore the solar system: Name a planet close to the sun.', 'science', 10, 0),
        ]
        c.executemany("INSERT OR IGNORE INTO posts (user_id, content, subject, likes, reported) VALUES (?, ?, ?, ?, ?)", bot_posts)
        conn.commit()
        print("Bot posts seeded")

    except sqlite3.Error as e:
        print(f"SQLite error in init_db: {e}")
        logger.error(f"SQLite error in init_db: {e}")
        conn.rollback()
        raise
    except Exception as e:
        print(f"DB init failed: {e}")
        logger.error(f"DB init failed: {e}")
        conn.rollback()
        raise

# Seed lessons (20 total, CAPS-aligned)
def seed_lessons():
    conn = get_db()
    c = conn.cursor()
    lessons = [
        (None, 1, 'math', 'Grade 1: Farm Addition<br>Solve: 2 + 3 = ?<br>Explanation: Imagine 2 apples + 3 more = 5!<br>Afrikaans: Graad 1: Plaas Optelling<br>Oplos: 2 + 3 = ?<br>Verduideliking: Stel jou voor 2 appels + 3 meer = 5!', 0),
        (None, 1, 'language', 'Grade 1: Farm Spelling<br>Spell "cat".<br>Hint: Sounds like /k/ /a/ /t/.<br>Afrikaans: Graad 1: Plaas Spelling<br>Spel "kat".<br>Wenk: Klink soos /k/ /a/ /t/.', 0),
        (None, 1, 'language', 'Grade 1: Phonics - M Sounds<br>Match words starting with M!<br>Afrikaans: Graad 1: Fonika - M Klanke<br>Pas woorde wat met M begin!<br>After this, play the Mars Memory Match game.', 0),
        (None, 2, 'science', 'Grade 2: Solar System<br>Name a planet in our solar system.<br>Explanation: Earth is our home!<br>Afrikaans: Graad 2: Sonnestelsel<br>Noem ’n planeet in ons sonnestelsel.<br>Verduideliking: Aarde is ons huis!', 0),
        (None, 2, 'math', 'Grade 2: Subtraction Adventure<br>Solve: 5 - 2 = ?<br>Explanation: Take away 2 from 5 leaves 3!<br>Afrikaans: Graad 2: Aftrek Avontuur<br>Oplos: 5 - 2 = ?<br>Verduideliking: Haal 2 uit 5 laat 3!', 0),
        (None, 3, 'language', 'Grade 3: Write a Story<br>Write a short sentence about the sun.<br>Example: The sun is bright and warm.<br>Afrikaans: Graad 3: Skryf ’n Storie<br>Skryf ’n kort sin oor die son.<br>Voorbeeld: Die son is helder en warm.', 0),
        (None, 1, 'science', 'Grade 1: Animals on the Farm<br>What sound does a cow make?<br>Afrikaans: Graad 1: Diere op die Plaas<br>Watter klank maak \'n koei?', 0),
        (None, 1, 'math', 'Grade 1: Counting Chickens<br>Count 1-5 chickens.<br>Afrikaans: Graad 1: Tel Hoenders<br>Tell 1-5 hoenders.', 0),
        (None, 2, 'language', 'Grade 2: Simple Sentences<br>Make a sentence with "dog".<br>Afrikaans: Graad 2: Eenvoudige Sinne<br>Maak \'n sin met "hond".', 0),
        (None, 2, 'science', 'Grade 2: Weather Words<br>What is rain?<br>Afrikaans: Graad 2: Weer Woorde<br>Wat is reën?', 0),
        (None, 3, 'math', 'Grade 3: Basic Multiplication<br>2 x 3 = ?<br>Afrikaans: Graad 3: Basiese Vermenigvuldiging<br>2 x 3 = ?', 0),
        (None, 3, 'language', 'Grade 3: Reading Comprehension<br>Read and answer: The cat sat on the mat.<br>Afrikaans: Graad 3: Leesbegrip<br>Lees en antwoord: Die kat het op die mat gesit.', 0),
        (None, 1, 'science', 'Grade 1: Colors in Nature<br>Name red things.<br>Afrikaans: Graad 1: Kleure in die Natuur<br>Noem rooi dinge.', 0),
        (None, 2, 'math', 'Grade 2: Shapes Around Us<br>Find circles.<br>Afrikaans: Graad 2: Vorms Om Ons<br>Vind sirkels.', 0),
        (None, 3, 'science', 'Grade 3: Human Body Basics<br>What do lungs do?<br>Afrikaans: Graad 3: Basiese Menslike Liggaam<br>Wat doen longe?', 0),
        (None, 1, 'language', 'Grade 1: Rhyming Words<br>Cat-hat.<br>Afrikaans: Graad 1: Rymwoorde<br>Kat-hoed.', 0),
        (None, 2, 'language', 'Grade 2: Vocabulary Builder<br>What is "happy"?<br>Afrikaans: Graad 2: Woordeskat Bouer<br>Wat is "gelukkig"?', 0),
        (None, 3, 'math', 'Grade 3: Fractions Intro<br>Half of a pizza.<br>Afrikaans: Graad 3: Breuke Inleiding<br>Die helfte van \'n pizza.', 0),
        (None, 1, 'math', 'Grade 1: Number Recognition<br>Point to 4.<br>Afrikaans: Graad 1: Getal Herkenning<br>Wys na 4.', 0),
        (None, 2, 'science', 'Grade 2: Plants Grow<br>What do plants need?<br>Afrikaans: Graad 2: Plante Groei<br>Wat het plante nodig?', 0),
    ]
    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lessons_unique ON lessons(grade, subject, content)')
        c.executemany("INSERT OR IGNORE INTO lessons (user_id, grade, subject, content, completed) VALUES (?, ?, ?, ?, ?)", lessons)
        conn.commit()
        logger.debug("Seeded lessons")
        print("Lessons seeded")
    except sqlite3.OperationalError as e:
        print(f"Seed lessons failed: {e}")
        logger.error(f"Seed lessons failed: {e}")
        conn.rollback()
        raise