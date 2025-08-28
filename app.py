import os
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import sqlite3
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

# Load .env file for local development
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Configure logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.addHandler(handler)

# # PayPal setup (commented out for clean build)
# PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
# PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
# PAYPAL_PRODUCT_ID = os.environ.get('PAYPAL_PRODUCT_ID')
# PAYPAL_PLAN_ID = os.environ.get('PAYPAL_PLAN_ID')

# Bad-word filter
BAD_WORDS = ['bad', 'word']
def filter_content(content):
    for word in BAD_WORDS:
        content = re.sub(rf'\b{word}\b', '***', content, flags=re.IGNORECASE)
    return content

# Get DB connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('edugrok.db', timeout=10)
        g.db.execute('PRAGMA journal_mode=WAL;')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Check database schema for QA
def check_db_schema():
    conn = get_db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = {col[1]: col[2] for col in c.fetchall()}
    expected = {
        'id': 'INTEGER', 'email': 'TEXT', 'password': 'TEXT',
        'grade': 'INTEGER', 'theme': 'TEXT', 'subscribed': 'BOOLEAN'
    }
    for col, col_type in expected.items():
        if col not in columns:
            logger.error(f"Users table missing column: {col}")
            raise ValueError(f"Users table schema is outdated. Missing column: {col}")
        if columns[col] != col_type:
            logger.error(f"Users table column {col} has wrong type: expected {col_type}, got {columns[col]}")
            raise ValueError(f"Users table column {col} type mismatch")
    for table in ['posts', 'lessons', 'tests']:
        c.execute(f"PRAGMA table_info({table})")
        if not c.fetchall():
            logger.error(f"Table {table} does not exist")
            raise ValueError(f"Table {table} missing")
    logger.debug("Database schema check passed")

# Initialize and migrate SQLite database
def init_db():
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col for col in c.fetchall()}
        if not columns:
            logger.debug("Creating users table")
            c.execute('''CREATE TABLE users 
                         (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, 
                          grade INTEGER, theme TEXT, subscribed BOOLEAN DEFAULT 0)''')
        else:
            missing_cols = [col for col in ['grade', 'theme'] if col not in columns]
            if missing_cols:
                logger.debug(f"Migrating users table to add columns: {missing_cols}")
                c.execute("DROP TABLE IF EXISTS users_new")
                c.execute('''CREATE TABLE users_new 
                             (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, 
                              grade INTEGER, theme TEXT, subscribed BOOLEAN DEFAULT 0)''')
                old_cols = [col for col in columns if col != 'id']
                old_cols_str = ', '.join(old_cols)
                insert_cols = old_cols + missing_cols
                insert_cols_str = ', '.join(insert_cols)
                defaults = ', '.join([col if col in old_cols else 'NULL' if col == 'grade' else "'astronaut'" if col == 'theme' else '0' for col in insert_cols])
                c.execute(f'''INSERT INTO users_new (id, {insert_cols_str})
                             SELECT id, {defaults} FROM users''')
                c.execute("SELECT id, password FROM users_new WHERE password NOT LIKE 'pbkdf2:sha256%'")
                for user_id, plaintext in c.fetchall():
                    hashed = generate_password_hash(plaintext)
                    c.execute("UPDATE users_new SET password = ? WHERE id = ?", (hashed, user_id))
                c.execute('DROP TABLE users')
                c.execute('ALTER TABLE users_new RENAME TO users')
                logger.debug("Migration completed")
        c.execute('''CREATE TABLE IF NOT EXISTS posts 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, subject TEXT, 
                      likes INTEGER DEFAULT 0, reported BOOLEAN DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, grade INTEGER, 
                      subject TEXT, content TEXT, completed BOOLEAN DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tests 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, grade INTEGER, 
                      score INTEGER, date TEXT)''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_reported_id ON posts(reported, id DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_user_grade_completed ON lessons(user_id, grade, completed)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tests_user_date ON tests(user_id, date)')
        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise

init_db()
check_db_schema()

# Seed CAPS-aligned lessons
def seed_lessons():
    conn = get_db()
    c = conn.cursor()
    lessons = [
        (None, 1, 'math', 'Grade 1: Addition (Solve: 2 + 3 = ?)', 0),
        (None, 2, 'language', 'Grade 2: Write a sentence about the sun.', 0),
        (None, 3, 'science', 'Grade 3: Name a planet in our solar system.', 0)
    ]
    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lessons_unique ON lessons(grade, subject, content)')
        c.executemany("INSERT OR IGNORE INTO lessons (user_id, grade, subject, content, completed) VALUES (?, ?, ?, ?, ?)", lessons)
        conn.commit()
        logger.debug("Seeded lessons successfully")
    except sqlite3.OperationalError as e:
        logger.error(f"Seed lessons failed: {e}")
        conn.rollback()
        raise

seed_lessons()

@app.route('/')
def home():
    logger.debug("Accessing home route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT p.id, p.content, p.subject, p.likes, u.email, p.reported FROM posts p JOIN users u ON p.user_id = u.id WHERE p.reported = 0 ORDER BY p.id DESC LIMIT 5")
    posts = [(pid, filter_content(content), subject, likes, email, reported) for pid, content, subject, likes, email, reported in c.fetchall()]
    c.execute("SELECT id, subject, content, completed FROM lessons WHERE user_id IS NULL OR user_id = ? AND grade = ? AND completed = 0 LIMIT 1", (session['user_id'], session.get('grade', 1)))
    lesson = c.fetchone()
    c.execute("SELECT id, grade, score, date FROM tests WHERE user_id = ? AND date > ?", (session['user_id'], datetime.now() - timedelta(days=7)))
    test = c.fetchone()
    return render_template('home.html', posts=posts, lesson=lesson, test=test, subscribed=session.get('subscribed', False), theme=session.get('theme', 'astronaut'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Accessing register route")
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        theme = request.form.get('theme', 'astronaut')
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            logger.error("Invalid email")
            return "Invalid email", 400
        if len(password) < 8:
            logger.error("Password too short")
            return "Password must be at least 8 characters", 400
        try:
            conn = get_db()
            c = conn.cursor()
            hashed_password = generate_password_hash(password)
            c.execute("INSERT INTO users (email, password, theme) VALUES (?, ?, ?)", (email, hashed_password, theme))
            conn.commit()
            user_id = c.lastrowid
            session['user_id'] = user_id
            session['email'] = email
            logger.debug(f"Registered user: {email}")
            return redirect(url_for('assess'))
        except sqlite3.IntegrityError:
            logger.error("Email already in use")
            return "Email already in use", 400
        except Exception as e:
            logger.error(f"Register failed: {e}")
            conn.rollback()
            raise
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("Accessing login route")
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, password, grade, theme, subscribed FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['grade'] = user[2]
                session['theme'] = user[3]
                session['subscribed'] = user[4]
                session['email'] = email
                logger.debug(f"Logged in user: {email}")
                return redirect(url_for('home'))
            logger.error("Invalid credentials")
            return "Invalid credentials", 401
        except Exception as e:
            logger.error(f"Login failed: {e}")
            conn.rollback()
            raise
    return render_template('login.html')

@app.route('/logout')
def logout():
    logger.debug("Logging out")
    session.clear()
    return redirect(url_for('login'))

@app.route('/post', methods=['POST'])
def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        return "Unauthorized", 401
    content = filter_content(request.form['content'])
    subject = request.form['subject']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {e}")
        conn.rollback()
        raise

@app.route('/like/<int:post_id>')
def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM user_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return "Already liked", 400
        c.execute("INSERT INTO user_likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Like post failed: {e}")
        conn.rollback()
        raise

@app.route('/report/<int:post_id>')
def report_post(post_id):
    logger.debug(f"Reporting post {post_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE posts SET reported = 1 WHERE id = ?", (post_id,))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Report post failed: {e}")
        conn.rollback()
        raise

@app.route('/assess', methods=['GET', 'POST'])
def assess():
    logger.debug("Accessing assess route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        correct_answers = ["5", "Hat", "Water", "Example4", "Example5", "Example6", "Example7", "Example8", "Example9", "Example10"]
        score = sum(1 for i in range(1, 11) if request.form.get(f'q{i}') == correct_answers[i-1])
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
            raise
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
    return render_template('assess.html', questions=questions)

@app.route('/complete_lesson/<int:lesson_id>')
def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {e}")
        conn.rollback()
        raise

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
            conn.commit()
            return redirect(url_for('game', score=score))
        except Exception as e:
            logger.error(f"Test failed: {e}")
            conn.rollback()
            raise
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        {"q": "Example Q2", "a": ["Example2", "Wrong", "Wrong"], "correct": "Example2"},
        {"q": "Example Q3", "a": ["Example3", "Wrong", "Wrong"], "correct": "Example3"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"},
    ]
    return render_template('test.html', questions=questions)

@app.route('/game')
def game():
    logger.debug("Accessing game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    score = int(request.args.get('score', 0))
    difficulty = 'easy' if score < 3 else 'hard'
    return render_template('game.html', difficulty=difficulty, theme=session.get('theme', 'astronaut'))

@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    logger.debug("Accessing subscribe route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('subscribe.html')

@app.route('/subscribe/activate/<subscription_id>', methods=['POST'])
def activate_subscription(subscription_id):
    logger.debug(f"Activating subscription {subscription_id}")
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(f"https://api-m.sandbox.paypal.com/v1/billing/subscriptions/{subscription_id}", headers=headers)
    if response.status_code == 200 and response.json()['status'] == 'ACTIVE':
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET subscribed = 1 WHERE id = ?", (session['user_id'],))
        conn.commit()
        session['subscribed'] = True
        logger.debug("Subscription activated")
        return jsonify({"success": True})
    logger.error("Subscription not active")
    return jsonify({"error": "Subscription not active"}), 400

def get_access_token():
    url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    auth = (PAYPAL_CLIENT_ID, os.environ['PAYPAL_CLIENT_SECRET'])
    response = requests.post(url, auth=auth, data={"grant_type": "client_credentials"})
    return response.json()['access_token']

@app.route('/subscribe/success')
def subscribe_success():
    logger.debug("Accessing subscribe success")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route('/subscribe/cancel')
def subscribe_cancel():
    logger.debug("Accessing subscribe cancel")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
