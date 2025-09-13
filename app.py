import os
import secrets
import shutil
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, g, send_from_directory, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import sqlite3
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import requests
import stripe  # For premium subs

# Load .env file for local development
load_dotenv()

# Stripe setup (for future monetization)
stripe.api_key = os.environ.get('STRIPE_KEY')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Configure secure session settings
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Configure logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Bad-word filter
BAD_WORDS = ['bad', 'word']
def filter_content(content):
    if not isinstance(content, str):
        return ""
    for word in BAD_WORDS:
        content = re.sub(rf'\b{word}\b', '***', content, flags=re.IGNORECASE)
    return content

# Get DB connection with persistent path
def get_db():
    if 'db' not in g:
        if 'RENDER' in os.environ:
            db_path = '/data/edugrok.db'
            print("Using Render persistent DB path: /data/edugrok.db")
            logger.info("Using Render persistent DB path: /data/edugrok.db")
            if not os.path.exists(db_path):
                print(f"DB not found at {db_path} - attempting to create")
                try:
                    with open(db_path, 'a'):
                        pass
                    print(f"Created DB file at {db_path}")
                    logger.info(f"Created DB file at {db_path}")
                except PermissionError as e:
                    print(f"Permission denied creating DB at {db_path}: {e}")
                    logger.error(f"Permission denied creating DB at {db_path}: {e}")
                    raise
        else:
            db_path = 'edugrok.db'
            print("Using local DB path: edugrok.db")
            logger.info("Using local DB path: edugrok.db")
            if not os.path.exists(db_path):
                print(f"DB not found at {db_path} - will init on first use")
        g.db = sqlite3.connect(db_path, timeout=10)
        g.db.execute('PRAGMA journal_mode=WAL;')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Force DB Reset/Migration
def reset_db():
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS badges")
        c.execute("DROP TABLE IF EXISTS user_points")
        c.execute("DROP TABLE IF EXISTS user_likes")
        c.execute("DROP TABLE IF EXISTS tests")
        c.execute("DROP TABLE IF EXISTS lessons")
        c.execute("DROP TABLE IF EXISTS posts")
        c.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        print("Dropped all tables - forcing fresh migration")
        logger.info("Force reset: Dropped all tables")
        init_db()
        seed_lessons()
        check_db_schema()
        print("DB reset complete - tables recreated and seeded")
        logger.info("Force reset complete")
    except Exception as e:
        print(f"DB reset failed: {e}")
        logger.error(f"DB reset failed: {e}")
        conn.rollback()
        raise

@app.route('/reset_db')
def reset_db_route():
    if 'user_id' not in session:
        return "Login required", 401
    reset_db()
    return redirect(url_for('home'))

# Check database schema for QA
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
            raise ValueError(f"Users table schema is outdated. Missing column: {col}")
        if columns[col] != col_type.split()[0]:
            logger.error(f"Users table column {col} has wrong type: expected {col_type}, got {columns[col]}")
            raise ValueError(f"Users table column {col} type mismatch")
    for table in ['posts', 'lessons', 'tests', 'user_likes', 'user_points', 'badges']:
        c.execute(f"PRAGMA table_info({table})")
        if not c.fetchall():
            logger.error(f"Table {table} does not exist")
            raise ValueError(f"Table {table} missing")
    logger.debug("Database schema check passed")
    print("Schema check passed")

# Initialize and migrate SQLite database
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
                logger.debug(f"Migrating users table to add columns: {missing_cols}")
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
                for user_id, plaintext in c.fetchall():
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
        skykidz_id = skykidz_row['id'] if skykidz_row else None
        c.execute("SELECT id FROM users WHERE email = 'grokedu@example.com'")
        grokedu_row = c.fetchone()
        grokedu_id = grokedu_row['id'] if grokedu_row else None

        # Check if bot users were inserted successfully
        if skykidz_id is None or grokedu_id is None:
            logger.error("Failed to retrieve bot user IDs. SkyKidz ID: %s, GrokEdu ID: %s", skykidz_id, grokedu_id)
            c.execute("SELECT email, id FROM users")
            users = c.fetchall()
            logger.debug("Current users in DB: %s", [(row['email'], row['id']) for row in users])
            raise ValueError(f"Bot user insertion failed. SkyKidz ID: {skykidz_id}, GrokEdu ID: {grokedu_id}")

        print(f"Bot user IDs retrieved: SkyKidz={skykidz_id}, GrokEdu={grokedu_id}")
        logger.debug("Bot user IDs retrieved: SkyKidz=%s, GrokEdu=%s", skykidz_id, grokedu_id)

        # Seed bot posts
        bot_posts = [
            (skykidz_id, 'Check out this fun farm math adventure! 2 cows + 3 chickens = ?', 'math', 5, 0),
            (grokedu_id, 'Explore the solar system: Name a planet close to the sun.', 'science', 10, 0),
        ]
        c.executemany("INSERT OR IGNORE INTO posts (user_id, content, subject, likes, reported) VALUES (?, ?, ?, ?, ?)", bot_posts)
        conn.commit()
        print("Bot posts seeded")

    except sqlite3.Error as e:
        print(f"SQLite error during init_db: {e}")
        logger.error(f"SQLite error during init_db: {e}")
        conn.rollback()
        raise
    except Exception as e:
        print(f"Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise

# Seed CAPS-aligned lessons with bilingual content (20 total for beta)
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
        logger.debug("Seeded lessons successfully")
        print("Lessons seeded")
    except sqlite3.OperationalError as e:
        print(f"Seed lessons failed: {e}")
        logger.error(f"Seed lessons failed: {e}")
        conn.rollback()
        raise

# Initialize database and seed data within app context
def init_app():
    with app.app_context():
        try:
            init_db()
            check_db_schema()
            seed_lessons()
            print("App initialized successfully - DB ready")
            logger.info("App initialized successfully - DB ready")
        except Exception as e:
            print(f"App init failed: {e}")
            logger.error(f"App init failed: {e}")
            raise

init_app()

@app.route('/')
def home():
    logger.debug("Accessing home route")
    print("Home route called")
    if 'user_id' not in session:
        print("No user session - redirecting to login")
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    print("Fetching posts...")
    c.execute("SELECT p.id, p.content, p.subject, p.likes, u.handle, p.reported FROM posts p JOIN users u ON p.user_id = u.id WHERE p.reported = 0 ORDER BY p.id DESC LIMIT 5")
    posts_data = c.fetchall()
    print(f"Fetched {len(posts_data)} posts from DB")
    posts = []
    user_id = session.get('user_id')
    for row in posts_data:
        post = dict(
            id=row['id'],
            content=filter_content(row['content']),
            subject=row['subject'],
            likes=row['likes'] if row['likes'] is not None else 0,
            handle=row['handle'],
            reported=row['reported']
        )
        if user_id:
            c.execute("SELECT 1 FROM user_likes WHERE user_id = ? AND post_id = ?", (user_id, row['id']))
            post['liked_by_user'] = c.fetchone() is not None
        else:
            post['liked_by_user'] = False
        posts.append(post)
    print(f"Processed {len(posts)} posts for template")
    c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 LIMIT 1", (session['user_id'], session.get('grade', 1)))
    lesson_row = c.fetchone()
    lesson = dict(lesson_row) if lesson_row else None
    print(f"Fetched lesson: {lesson['subject'] if lesson else 'None'}")
    c.execute("SELECT id, grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (session['user_id'],))
    test_row = c.fetchone()
    test = dict(test_row) if test_row else None
    print(f"Fetched test: {test['score'] if test else 'None'}")
    return render_template('home.html.j2', posts=posts, lesson=lesson, test=test, subscribed=session.get('subscribed', False), theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/landing')
def landing():
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Accessing register route")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        theme = request.form.get('theme', 'astronaut')
        language = request.form.get('language', 'en')
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, theme, handle, language) VALUES (?, ?, ?, ?, ?)", (email, hashed_password, theme, email, language))
            conn.commit()
            user_id = c.lastrowid
            session['user_id'] = user_id
            session['email'] = email
            session['theme'] = theme
            session['language'] = language
            logger.debug(f"Registered user: {email}")
            return redirect(url_for('assess'))
        except sqlite3.IntegrityError:
            logger.error("Email already in use")
            return render_template('register.html.j2', error="Email already in use", theme=theme, language=language)
        except Exception as e:
            logger.error(f"Register failed: {e}")
            conn.rollback()
            return render_template('register.html.j2', error="Server error", theme=theme, language=language)
    return render_template('register.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("Accessing login route")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, password, grade, theme, subscribed, language FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['grade'] = user['grade']
                session['theme'] = user['theme']
                session['subscribed'] = bool(user['subscribed'])
                session['email'] = email
                session['language'] = user['language']
                logger.debug(f"Logged in user: {email}")
                return redirect(url_for('home'))
            logger.error("Invalid credentials")
            return render_template('login.html.j2', error="Invalid credentials", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        except Exception as e:
            logger.error(f"Login failed: {e}")
            conn.rollback()
            return render_template('login.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    return render_template('login.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/logout')
def logout():
    logger.debug("Logging out")
    session.clear()
    return redirect(url_for('landing'))

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = request.form.get('theme')
    if theme not in ['farm', 'space', 'astronaut']:
        flash('Invalid theme', 'error')
        return redirect(request.referrer or url_for('home'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, session['user_id']))
        conn.commit()
        session['theme'] = theme
        logger.info(f"Theme updated to {theme} for user {session['user_id']}")
        return redirect(request.referrer or url_for('home'))
    except Exception as e:
        logger.error(f"Theme update failed: {e}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(request.referrer or url_for('home'))

@app.route('/set_language', methods=['POST'])
def set_language():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    language = request.form.get('language')
    if language not in ['en', 'bilingual']:
        flash('Invalid language', 'error')
        return redirect(request.referrer or url_for('home'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE id = ?", (language, session['user_id']))
        conn.commit()
        session['language'] = language
        logger.info(f"Language updated to {language} for user {session['user_id']}")
        return redirect(request.referrer or url_for('home'))
    except Exception as e:
        logger.error(f"Language update failed: {e}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(request.referrer or url_for('home'))

@app.route('/post', methods=['POST'])
def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    content = filter_content(request.form.get('content', ''))
    subject = request.form.get('subject', '')
    if not content or not subject:
        return render_template('home.html.j2', error="Content and subject are required", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM user_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return render_template('home.html.j2', error="Already liked", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        c.execute("INSERT INTO user_likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Like post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/report/<int:post_id>')
def report_post(post_id):
    logger.debug(f"Reporting post {post_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE posts SET reported = 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Report post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/assess', methods=['GET', 'POST'])
def assess():
    logger.debug("Accessing assess route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        correct_answers = ["5", "Hat", "Water", "Example4", "Example5", "Example6", "Example7", "Example8", "Example9", "Example10"]
        score = sum(1 for i in range(1, 11) if request.form.get(f'q{i}') == correct_answers[i-1])
        grade = 1 if score < 4 else 2 if score < 7 else 3
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET grade = ? WHERE id = ?", (grade, session['user_id']))
            conn.commit()
            session['grade'] = grade
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Assess failed: {e}")
            conn.rollback()
            return render_template('assess.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    questions = [
        {"q": "Math: 2 + 3 = ?", "a": ["5", "6", "4"], "correct": "5"},
        {"q": "Language: Pick a word that rhymes with 'cat'.", "a": ["Hat", "Dog", "Car"], "correct": "Hat"},
        {"q": "Science: What do plants need to grow?", "a": ["Water", "Sand", "Rocks"], "correct": "Water"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"},
        {"q": "Example Q6", "a": ["Example6", "Wrong", "Wrong"], "correct": "Example6"},
        {"q": "Example Q7", "a": ["Example7", "Wrong", "Wrong"], "correct": "Example7"},
        {"q": "Example Q8", "a": ["Example8", "Wrong", "Wrong"], "correct": "Example8"},
        {"q": "Example Q9", "a": ["Example9", "Wrong", "Wrong"], "correct": "Example9"},
        {"q": "Example Q10", "a": ["Example10", "Wrong", "Wrong"], "correct": "Example10"},
    ]
    return render_template('assess.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/complete_lesson/<int:lesson_id>')
def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + 5)", (session['user_id'], session['user_id']))
        # Award 'Lesson Master' badge if first 5 lessons
        c.execute("SELECT COUNT(*) FROM badges WHERE user_id = ? AND badge_name = 'Lesson Master'", (session['user_id'],))
        if c.fetchone()[0] == 0:
            c.execute("SELECT COUNT(*) FROM lessons WHERE user_id = ? AND completed = 1", (session['user_id'],))
            if c.fetchone()[0] >= 5:
                c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, 'Lesson Master', ?)", (session['user_id'], datetime.now().isoformat()))
        conn.commit()
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {e}")
        conn.rollback()
        return render_template('lessons.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/test', methods=['GET', 'POST'])
def take_test():
    logger.debug("Accessing test route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        correct_answers = ["9", "Example2", "Example3", "Example4", "Example5"]
        score = sum(1 for i in range(1, 6) if request.form.get(f'q{i}') == correct_answers[i-1])
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO tests (user_id, grade, score, date) VALUES (?, ?, ?, ?)", 
                      (session['user_id'], session['grade'], score, datetime.now().isoformat()))
            points_award = score * 2
            c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", (session['user_id'], session['user_id'], points_award))
            conn.commit()
            return redirect(url_for('game', score=score))
        except Exception as e:
            logger.error(f"Test failed: {e}")
            conn.rollback()
            return render_template('test.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        {"q": "Example Q2", "a": ["Example2", "Wrong", "Wrong"], "correct": "Example2"},
        {"q": "Example Q3", "a": ["Example3", "Wrong", "Wrong"], "correct": "Example3"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"},
    ]
    return render_template('test.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/game')
def game():
    logger.debug("Accessing game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    score = int(request.args.get('score', 0))
    difficulty = 'easy' if score < 3 else 'hard'
    return render_template('game.html.j2', difficulty=difficulty, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'), score=score)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id = ? OR user_id IS NULL) AND completed = 1 AND grade = ?", (session['user_id'], session['grade']))
        lessons_completed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id = ? OR user_id IS NULL) AND grade = ?", (session['user_id'], session['grade']))
        total_lessons = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tests WHERE user_id = ?", (session['user_id'],))
        games_played = c.fetchone()[0]
        c.execute("SELECT AVG(score) FROM tests WHERE user_id = ?", (session['user_id'],))
        avg_score = round(c.fetchone()[0] or 0, 1)
        grade_letter = 'A' if session['grade'] >= 3 else 'B' if session['grade'] == 2 else 'C'
        c.execute("SELECT points FROM user_points WHERE user_id = ?", (session['user_id'],))
        result = c.fetchone()
        points = result['points'] if result else 0
        c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ?", (session['user_id'],))
        badges = [dict(row) for row in c.fetchall()]
        return render_template('profile.html.j2', 
                              lessons_completed=f"{lessons_completed}/{total_lessons}",
                              games_played=games_played,
                              avg_score=avg_score,
                              grade=grade_letter,
                              theme=session['theme'],
                              language=session.get('language', 'en'),
                              points=points,
                              badges=badges)
    except Exception as e:
        logger.error(f"Profile route failed: {e} - Session: {session}")
        print(f"Profile error: {e}")
        return render_template('error.html.j2', error="Failed to load profile. Try resetting DB.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.route('/parent_dashboard')
def parent_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT 
                COUNT(*) as total_lessons,
                SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) as completed_lessons,
                AVG(t.score) as avg_test_score,
                COALESCE(p.points, 0) as total_points,
                (SELECT COUNT(*) FROM badges WHERE user_id = ?) as badges_count
            FROM lessons l 
            LEFT JOIN tests t ON l.user_id = t.user_id AND l.grade = t.grade
            LEFT JOIN user_points p ON l.user_id = p.user_id
            WHERE l.user_id = ? AND l.grade = ?
        """, (session['user_id'], session['user_id'], session['grade']))
        stats = c.fetchone()
        return render_template('parent_dashboard.html.j2', stats=stats, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Parent dashboard failed: {e}")
        return render_template('error.html.j2', error="Failed to load dashboard.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.route('/lessons')
def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? ORDER BY completed", (session['user_id'], session['grade']))
    lessons_list = [dict(row) for row in c.fetchall()]
    return render_template('lessons.html.j2', lessons=lessons_list, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/update_points', methods=['POST'])
def update_points():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        points_award = int(data.get('points', 0))
        if points_award <= 0 or points_award > 20:
            return jsonify({'success': False, 'error': 'Invalid points'}), 400
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", 
                  (session['user_id'], session['user_id'], points_award))
        conn.commit()
        logger.info(f"Awarded {points_award} points to user {session['user_id']}")
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Update points failed: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/phonics_game')
def phonics_game():
    logger.debug("Accessing phonics game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('phonics_game.html.j2', theme=session.get('theme', 'astronaut'), grade=session.get('grade', 1), language=session.get('language', 'en'))

@app.route('/generate_lesson', methods=['POST'])
def generate_lesson():
    logger.debug("Accessing generate_lesson route")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    grade = request.form.get('grade')
    subject = request.form.get('subject')
    if not grade or not subject or not grade.isdigit() or int(grade) not in [1, 2, 3]:
        logger.error("Invalid grade or subject")
        return render_template('lessons.html.j2', error="Invalid grade (1-3) or subject", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        api_url = "https://x.ai/api"
        headers = {"Authorization": "Bearer YOUR_API_KEY_HERE"}
        payload = {
            "grade": int(grade),
            "subject": subject,
            "language": "en"
        }
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        lesson_content = response.json().get("content", f"Generated {subject} lesson for Grade {grade}")
        if session.get('language') == 'bilingual':
            lesson_content += f"<br>Afrikaans: Gegenereerde {subject} les vir Graad {grade}"
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO lessons (user_id, grade, subject, content, completed) VALUES (?, ?, ?, ?, 0)", 
                  (session['user_id'], grade, subject, lesson_content))
        conn.commit()
        logger.info(f"Generated lesson for user {session['user_id']}: {subject}")
        return redirect(url_for('lessons'))
    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {e}")
        return render_template('lessons.html.j2', error="Failed to generate lesson - check API", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Generate lesson failed: {e}")
        conn.rollback()
        return render_template('lessons.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/beta', methods=['GET', 'POST'])
def beta():
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            logger.info(f"Beta invite requested: {email}")
            flash('Thanks! You\'re on the beta list. Check your email soon.', 'success')
        return redirect(url_for('landing'))
    return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/award_badge/<badge_name>')
def award_badge(badge_name):
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, ?, ?)", 
                  (session['user_id'], badge_name, datetime.now().isoformat()))
        conn.commit()
        logger.info(f"Awarded badge '{badge_name}' to user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Award badge failed: {e}")
        return jsonify({'success': False}), 500

@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            # Stub: Create Stripe checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'zar',
                        'product_data': {'name': 'EduGrok Premium'},
                        'unit_amount': 7900,  # R79.00
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('home', _external=True),
                cancel_url=url_for('parent_dashboard', _external=True),
            )
            return redirect(session.url, code=303)
        except Exception as e:
            logger.error(f"Stripe checkout failed: {e}")
            flash('Subscription failed. Try again.', 'error')
            return redirect(url_for('parent_dashboard'))
    return render_template('subscribe.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Enhanced error handling
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal Server Error: {error} - Request: {request.url} - Session: {session}")
    print(f"Internal Error: {error}")
    return render_template('error.html.j2', error="Failed to load feed. Please try again.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 Not Found: {request.url}")
    print(f"404 Not Found: {request.url}")
    return render_template('error.html.j2', error="Page not found.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 404

# Log all requests
@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.url} - User ID: {session.get('user_id', 'None')}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))