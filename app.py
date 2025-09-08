import os
import secrets
import shutil
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import sqlite3
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

from flask import request, redirect, url_for, flash
from flask_login import login_required
import requests
import logging
from datetime import datetime
from your_models import Lesson, db  # Assuming Lesson model and db from SQLAlchemy


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load .env file for local development
load_dotenv()

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
        # Detect environment: Render sets RENDER=true
        if 'RENDER' in os.environ:
            db_path = '/data/edugrok.db'
            print("Using Render persistent DB path: /data/edugrok.db")
            logger.info("Using Render persistent DB path: /data/edugrok.db")
        else:
            db_path = 'edugrok.db'  # Local fallback to current dir
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

# Force DB Reset/Migration (temporary for local fix)
def reset_db():
    conn = get_db()
    c = conn.cursor()
    try:
        # Drop all tables
        c.execute("DROP TABLE IF EXISTS user_points")
        c.execute("DROP TABLE IF EXISTS user_likes")
        c.execute("DROP TABLE IF EXISTS tests")
        c.execute("DROP TABLE IF EXISTS lessons")
        c.execute("DROP TABLE IF EXISTS posts")
        c.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        print("Dropped all tables - forcing fresh migration")
        logger.info("Force reset: Dropped all tables")
        
        # Recreate via init_db
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
        'handle': 'TEXT'
    }
    for col, col_type in expected.items():
        if col not in columns:
            logger.error(f"Users table missing column: {col}")
            raise ValueError(f"Users table schema is outdated. Missing column: {col}")
        if columns[col] != col_type.split()[0]:
            logger.error(f"Users table column {col} has wrong type: expected {col_type}, got {columns[col]}")
            raise ValueError(f"Users table column {col} type mismatch")
    for table in ['posts', 'lessons', 'tests', 'user_likes', 'user_points']:
        c.execute(f"PRAGMA table_info({table})")
        if not c.fetchall():
            logger.error(f"Table {table} does not exist")
            raise ValueError(f"Table {table} missing")
    logger.debug("Database schema check passed")
    print("Schema check passed")

# Initialize and migrate SQLite database (called in reset/init)
def init_db():
    conn = get_db()
    c = conn.cursor()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchall()[0][2]  # Get current DB path
        print(f"Initializing DB at {db_path}")
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col for col in c.fetchall()}
        if not columns:
            logger.debug("Creating users table")
            c.execute('''CREATE TABLE users 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                          grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT)''')
        else:
            missing_cols = [col for col in ['grade', 'theme', 'subscribed', 'handle'] if col not in columns]
            if missing_cols:
                logger.debug(f"Migrating users table to add columns: {missing_cols}")
                c.execute("DROP TABLE IF EXISTS users_new")
                c.execute('''CREATE TABLE users_new 
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, 
                              grade INTEGER, theme TEXT, subscribed INTEGER DEFAULT 0, handle TEXT)''')
                old_cols = [col for col in columns if col != 'id']
                insert_cols = old_cols + missing_cols
                insert_cols_str = ', '.join(insert_cols)
                select_cols = ', '.join([col if col in old_cols else 'NULL' if col == 'grade' else "'astronaut'" if col == 'theme' else '0' if col == 'subscribed' else "email" for col in insert_cols])
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_reported_id ON posts(reported, id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_user_grade_completed ON lessons(user_id, grade, completed)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tests_user_date ON tests(user_id, date)')
        conn.commit()
        print("Tables created/updated")

        # Seed bot users
        bots = [
            ('skykidz@example.com', generate_password_hash('botpass'), 1, 'farm', 0, 'SkyKidz'),
            ('grokedu@example.com', generate_password_hash('botpass'), 2, 'space', 0, 'GrokEdu'),
        ]
        c.executemany("INSERT OR IGNORE INTO users (email, password, grade, theme, subscribed, handle) VALUES (?, ?, ?, ?, ?, ?)", bots)
        conn.commit()
        print("Bot users seeded")

        # Get bot IDs
        c.execute("SELECT id FROM users WHERE email = 'skykidz@example.com'")
        skykidz_id = c.fetchone()[0]
        c.execute("SELECT id FROM users WHERE email = 'grokedu@example.com'")
        grokedu_id = c.fetchone()[0]

        # Seed bot posts
        bot_posts = [
            (skykidz_id, 'Check out this fun farm math adventure! 2 cows + 3 chickens = ?', 'math', 5, 0),
            (grokedu_id, 'Explore the solar system: Name a planet close to the sun.', 'science', 10, 0),
        ]
        c.executemany("INSERT OR IGNORE INTO posts (user_id, content, subject, likes, reported) VALUES (?, ?, ?, ?, ?)", bot_posts)
        conn.commit()
        print("Bot posts seeded")

    except Exception as e:
        print(f"Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise

# Seed CAPS-aligned lessons
def seed_lessons():
    conn = get_db()
    c = conn.cursor()
    lessons = [
        (None, 1, 'math', 'Grade 1: Farm Addition<br>Solve: 2 + 3 = ?<br>Explanation: Imagine 2 apples + 3 more = 5!<br><video controls><source src="/static/mock-farm-video.mp4" type="video/mp4"></video>', 0),
        (None, 1, 'language', 'Grade 1: Farm Spelling<br>Spell "cat".<br>Hint: Sounds like /k/ /a/ /t/.<br><img src="/static/cat.png">', 0),
        (None, 1, 'language', 'Grade 1: Phonics - M Sounds<br>Match words starting with M!<br>After this, play the Mars Memory Match game.', 0),
        (None, 2, 'science', 'Grade 2: Solar System<br>Name a planet in our solar system.<br>Explanation: Earth is our home!<br><iframe width="560" height="315" src="https://www.youtube.com/embed/mock-video" title="Planet Explanation" frameborder="0" allowfullscreen></iframe>', 0),
        (None, 2, 'math', 'Grade 2: Subtraction Adventure<br>Solve: 5 - 2 = ?<br>Explanation: Take away 2 from 5 leaves 3!<br><video controls><source src="/static/mock-sub-video.mp4" type="video/mp4"></video>', 0),
        (None, 3, 'language', 'Grade 3: Write a Story<br>Write a short sentence about the sun.<br>Example: The sun is bright and warm.', 0),
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
    return render_template('home.html.j2', posts=posts, lesson=lesson, test=test, subscribed=session.get('subscribed', False), theme=session.get('theme', 'astronaut'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Accessing register route")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        theme = request.form.get('theme', 'astronaut')
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, theme, handle) VALUES (?, ?, ?, ?)", (email, hashed_password, theme, email))
            conn.commit()
            user_id = c.lastrowid
            session['user_id'] = user_id
            session['email'] = email
            session['theme'] = theme
            logger.debug(f"Registered user: {email}")
            return redirect(url_for('assess'))
        except sqlite3.IntegrityError:
            logger.error("Email already in use")
            return render_template('register.html.j2', error="Email already in use", theme=theme)
        except Exception as e:
            logger.error(f"Register failed: {e}")
            conn.rollback()
            return render_template('register.html.j2', error="Server error", theme=theme)
    return render_template('register.html.j2', theme=session.get('theme', 'astronaut'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("Accessing login route")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, password, grade, theme, subscribed FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['grade'] = user['grade']
                session['theme'] = user['theme']
                session['subscribed'] = bool(user['subscribed'])
                session['email'] = email
                logger.debug(f"Logged in user: {email}")
                return redirect(url_for('home'))
            logger.error("Invalid credentials")
            return render_template('login.html.j2', error="Invalid credentials", theme=session.get('theme', 'astronaut'))
        except Exception as e:
            logger.error(f"Login failed: {e}")
            conn.rollback()
            return render_template('login.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))
    return render_template('login.html.j2', theme=session.get('theme', 'astronaut'))

@app.route('/logout')
def logout():
    logger.debug("Logging out")
    session.clear()
    return redirect(url_for('login'))

@app.route('/post', methods=['POST'])
def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'))
    content = filter_content(request.form.get('content', ''))
    subject = request.form.get('subject', '')
    if not content or not subject:
        return render_template('home.html.j2', error="Content and subject are required", theme=session.get('theme', 'astronaut'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM user_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return render_template('home.html.j2', error="Already liked", theme=session.get('theme', 'astronaut'))
        c.execute("INSERT INTO user_likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Like post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))

@app.route('/report/<int:post_id>')
def report_post(post_id):
    logger.debug(f"Reporting post {post_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE posts SET reported = 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Report post failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))

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
            return render_template('assess.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'))
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
    return render_template('assess.html.j2', questions=questions, theme=session.get('theme', 'astronaut'))

@app.route('/complete_lesson/<int:lesson_id>')
def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + 5)", (session['user_id'], session['user_id']))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))

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
            return render_template('test.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'))
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        {"q": "Example Q2", "a": ["Example2", "Wrong", "Wrong"], "correct": "Example2"},
        {"q": "Example Q3", "a": ["Example3", "Wrong", "Wrong"], "correct": "Example3"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"},
    ]
    return render_template('test.html.j2', questions=questions, theme=session.get('theme', 'astronaut'))

@app.route('/game')
def game():
    logger.debug("Accessing game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    score = int(request.args.get('score', 0))
    difficulty = 'easy' if score < 3 else 'hard'
    return render_template('game.html.j2', difficulty=difficulty, theme=session.get('theme', 'astronaut'), score=score)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
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
    return render_template('profile.html.j2', 
                           lessons_completed=f"{lessons_completed}/{total_lessons}",
                           games_played=games_played,
                           avg_score=avg_score,
                           grade=grade_letter,
                           theme=session['theme'],
                           points=points)

@app.route('/lessons')
def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? ORDER BY completed", (session['user_id'], session['grade']))
    lessons_list = [dict(row) for row in c.fetchall()]
    return render_template('lessons.html.j2', lessons=lessons_list, theme=session.get('theme', 'astronaut'))

@app.route('/update_points')
def update_points():
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'))
    points_award = int(request.args.get('points', 0))
    if points_award <= 0 or points_award > 20:
        return render_template('home.html.j2', error="Invalid points", theme=session.get('theme', 'astronaut'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", 
                  (session['user_id'], session['user_id'], points_award))
        conn.commit()
        return "Points updated", 200
    except Exception as e:
        logger.error(f"Update points failed: {e}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'))

@app.route('/phonics_game')
def phonics_game():
    logger.debug("Accessing phonics game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('phonics_game.html.j2', theme=session['theme'], grade=session['grade'])

@app.route('/generate_lesson', methods=['POST'])
@login_required
def generate_lesson():
    try:
        data = request.form
        grade = data.get('grade')
        subject = data.get('subject')

        if not grade or not subject:
            flash('Grade and subject are required!', 'error')
            return redirect(url_for('lessons'))

        # Placeholder xAI API call
        api_url = 'https://x.ai/api'  # Update with actual endpoint
        headers = {'Authorization': 'Bearer YOUR_XAI_API_KEY'}  # Replace with secure key
        payload = {
            'grade': grade,
            'subject': subject,
            'curriculum': 'CAPS'
        }

        logger.info(f"Requesting lesson generation for grade {grade}, subject {subject}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.error(f"xAI API request failed: {response.status_code} - {response.text}")
            flash('Failed to generate lesson. Please try again later.', 'error')
            return redirect(url_for('lessons'))

        lesson_data = response.json()
        lesson_content = lesson_data.get('content', 'No content provided')
        lesson_title = lesson_data.get('title', f'{subject} Lesson for Grade {grade}')

        # Insert into lessons table
        new_lesson = Lesson(
            title=lesson_title,
            subject=subject,
            content=lesson_content,
            grade=grade,
            user_id=current_user.id,  # Assuming Flask-Login
            created_at=datetime.utcnow(),
            completed=False
        )
        db.session.add(new_lesson)
        db.session.commit()

        logger.info(f"Lesson '{lesson_title}' created for user {current_user.id}")
        flash('Lesson generated successfully!', 'success')
        return redirect(url_for('lessons'))

    except requests.RequestException as e:
        logger.error(f"API call failed: {str(e)}")
        flash('Error connecting to lesson generation service.', 'error')
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Error generating lesson: {str(e)}")
        db.session.rollback()
        flash('An unexpected error occurred.', 'error')
        return redirect(url_for('lessons'))

# Enhanced error handling
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal Server Error: {error} - Request: {request.url} - Session: {session}")
    print(f"Internal Error: {error}")
    return render_template('error.html.j2', error="Failed to load feed. Please try again."), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 Not Found: {request.url}")
    print(f"404 Not Found: {request.url}")
    return render_template('error.html.j2', error="Page not found."), 404

# Log all requests
@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.url} - User ID: {session.get('user_id', 'None')}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))