import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import paypalrestsdk
import sqlite3
import re
import logging
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-for-local-testing')

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# PayPal setup
paypalrestsdk.configure({
    "mode": "sandbox",
    "client_id": os.environ.get('PAYPAL_CLIENT_ID', 'your_paypal_client_id'),
    "client_secret": os.environ.get('PAYPAL_CLIENT_SECRET', 'your_paypal_secret')
})

# Bad-word filter
BAD_WORDS = ['bad', 'word']
def filter_content(content):
    for word in BAD_WORDS:
        content = re.sub(rf'\b{word}\b', '***', content, flags=re.IGNORECASE)
    return content

# Check database schema for QA
def check_db_schema():
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    # Check users table columns
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    expected = ['id', 'email', 'password', 'grade', 'theme', 'subscribed']
    if set(columns) != set(expected):
        logger.error(f"Users table schema mismatch. Expected: {expected}, Found: {columns}")
        raise ValueError("Users table schema is outdated. Run migration.")
    # Check other tables (simplified)
    for table in ['posts', 'lessons', 'tests']:
        c.execute(f"PRAGMA table_info({table})")
        if not c.fetchall():
            logger.error(f"Table {table} does not exist")
            raise ValueError(f"Table {table} missing")
    conn.close()
    logger.debug("Database schema check passed")

# Initialize and migrate SQLite database
def init_db():
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    # Check if users table exists and its schema
    c.execute("PRAGMA table_info(users)")
    columns = {col[1]: col for col in c.fetchall()}
    if not columns:
        # Create users table if it doesn't exist
        c.execute('''CREATE TABLE users 
                     (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, grade INTEGER, theme TEXT, subscribed BOOLEAN DEFAULT 0)''')
    elif 'theme' not in columns:
        # Migrate: Create new table, copy data, drop old
        logger.debug("Migrating users table to add theme column")
        c.execute('''CREATE TABLE users_new 
                     (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, grade INTEGER, theme TEXT, subscribed BOOLEAN DEFAULT 0)''')
        c.execute('''INSERT INTO users_new (id, email, password, grade, subscribed)
                     SELECT id, email, password, grade, subscribed FROM users''')
        c.execute('DROP TABLE users')
        c.execute('ALTER TABLE users_new RENAME TO users')
    # Create other tables
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, subject TEXT, likes INTEGER DEFAULT 0, reported BOOLEAN DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, grade INTEGER, subject TEXT, content TEXT, completed BOOLEAN DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tests 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, grade INTEGER, score INTEGER, date TEXT)''')
    conn.commit()
    conn.close()

init_db()
check_db_schema()  # Run QA check on startup

# Seed CAPS-aligned lessons
def seed_lessons():
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    lessons = [
        (None, 1, 'math', 'Grade 1: Addition (Solve: 2 + 3 = ?)', 0),
        (None, 2, 'language', 'Grade 2: Write a sentence about the sun.', 0),
        (None, 3, 'science', 'Grade 3: Name a planet in our solar system.', 0)
    ]
    try:
        c.executemany("INSERT OR IGNORE INTO lessons (user_id, grade, subject, content, completed) VALUES (?, ?, ?, ?, ?)", lessons)
        conn.commit()
        logger.debug("Seeded lessons successfully")
    except sqlite3.OperationalError as e:
        logger.error(f"Seed lessons failed: {e}")
        raise
    finally:
        conn.close()

seed_lessons()

@app.route('/')
def home():
    logger.debug("Accessing home route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("SELECT p.id, p.content, p.subject, p.likes, u.email, p.reported FROM posts p JOIN users u ON p.user_id = u.id WHERE p.reported = 0 ORDER BY p.id DESC LIMIT 5")
    posts = [(pid, filter_content(content), subject, likes, email, reported) for pid, content, subject, likes, email, reported in c.fetchall()]
    c.execute("SELECT id, subject, content, completed FROM lessons WHERE user_id = ? AND grade = ? AND completed = 0 LIMIT 1", (session['user_id'], session.get('grade', 1)))
    lesson = c.fetchone()
    c.execute("SELECT id, grade, score, date FROM tests WHERE user_id = ? AND date > ?", (session['user_id'], (datetime.now() - timedelta(days=7)).isoformat()))
    test = c.fetchone()
    conn.close()
    return render_template('home.html', posts=posts, lesson=lesson, test=test, subscribed=session.get('subscribed', False), theme=session.get('theme', 'astronaut'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Accessing register route")
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        theme = request.form.get('theme', 'astronaut')
        try:
            conn = sqlite3.connect('edugrok.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL;')
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, theme) VALUES (?, ?, ?)", (email, password, theme))
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            session['user_id'] = user_id
            session['email'] = email
            logger.debug(f"Registered user: {email}")
            return redirect(url_for('assess'))
        except sqlite3.IntegrityError:
            logger.error("Email already in use")
            return "Email already in use", 400
        except Exception as e:
            logger.error(f"Register failed: {e}")
            raise
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("Accessing login route")
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            conn = sqlite3.connect('edugrok.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL;')
            c = conn.cursor()
            c.execute("SELECT id, grade, theme, subscribed FROM users WHERE email = ? AND password = ?", (email, password))
            user = c.fetchone()
            conn.close()
            if user:
                session['user_id'] = user[0]
                session['grade'] = user[1]
                session['theme'] = user[2]
                session['subscribed'] = user[3]
                session['email'] = email
                logger.debug(f"Logged in user: {email}")
                return redirect(url_for('home'))
            logger.error("Invalid credentials")
            return "Invalid credentials", 401
        except Exception as e:
            logger.error(f"Login failed: {e}")
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
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/like/<int:post_id>')
def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/report/<int:post_id>')
def report_post(post_id):
    logger.debug(f"Reporting post {post_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("UPDATE posts SET reported = 1 WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/assess', methods=['GET', 'POST'])
def assess():
    logger.debug("Accessing assess route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        score = sum(int(request.form.get(f'q{i}', 0)) for i in range(1, 11))
        grade = 1 if score < 4 else 2 if score < 7 else 3
        conn = sqlite3.connect('edugrok.db', timeout=10)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute("UPDATE users SET grade = ? WHERE id = ?", (grade, session['user_id']))
        conn.commit()
        conn.close()
        session['grade'] = grade
        return redirect(url_for('home'))
    questions = [
        {"q": "Math: 2 + 3 = ?", "a": ["5", "6", "4"], "correct": "5"},
        {"q": "Language: Pick a word that rhymes with 'cat'.", "a": ["Hat", "Dog", "Car"], "correct": "Hat"},
        {"q": "Science: What do plants need to grow?", "a": ["Water", "Sand", "Rocks"], "correct": "Water"},
        # Placeholder for 7 more
    ]
    return render_template('assess.html', questions=questions)

@app.route('/complete_lesson/<int:lesson_id>')
def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        return "Unauthorized", 401
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND user_id = ?", (lesson_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/test', methods=['GET', 'POST'])
def take_test():
    logger.debug("Accessing test route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        score = sum(int(request.form.get(f'q{i}', 0)) for i in range(1, 6))
        conn = sqlite3.connect('edugrok.db', timeout=10)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute("INSERT INTO tests (user_id, grade, score, date) VALUES (?, ?, ?, ?)", 
                  (session['user_id'], session['grade'], score, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return redirect(url_for('game', score=score))
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        # Placeholder for 4 more
    ]
    return render_template('test.html', questions=questions)

@app.route('/game/<int:score>')
def game(score):
    logger.debug(f"Accessing game with score {score}")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    difficulty = 'easy' if score < 3 else 'hard'
    return render_template('game.html', difficulty=difficulty, theme=session.get('theme', 'astronaut'))

@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    logger.debug("Accessing subscribe route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = session.get('email')
        try:
            plan = paypalrestsdk.BillingPlan({
                "name": "EduGrok Premium",
                "description": "$5/month for premium content",
                "type": "FIXED",
                "payment_definitions": [{
                    "type": "REGULAR",
                    "frequency": "MONTH",
                    "amount": {"value": "5", "currency": "USD"},
                    "cycles": "12",
                    "frequency_interval": "1"
                }],
                "merchant_preferences": {
                    "return_url": "http://edugrok-v1-2.onrender.com/subscribe/success",
                    "cancel_url": "http://edugrok-v1-2.onrender.com/subscribe/cancel"
                }
            })
            if plan.create():
                agreement = paypalrestsdk.BillingAgreement({
                    "name": "EduGrok Subscription",
                    "description": "Monthly subscription for EduGrok",
                    "start_date": (datetime.now() + timedelta(days=1)).isoformat(),
                    "plan": {"id": plan.id},
                    "payer": {"payment_method": "paypal"},
                    "shipping_address": None
                })
                if agreement.create():
                    for link in agreement.links:
                        if link.rel == "approval_url":
                            return redirect(link.href)
            logger.error("Failed to create subscription")
            return jsonify({"error": "Failed to create subscription"}), 400
        except paypalrestsdk.exceptions.ResourceError as e:
            logger.error(f"Subscribe failed: {e}")
            return jsonify({"error": str(e)}), 400
    return render_template('subscribe.html')

@app.route('/subscribe/success')
def subscribe_success():
    logger.debug("Accessing subscribe success")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('edugrok.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    c.execute("UPDATE users SET subscribed = 1 WHERE id = ?", (session['user_id'],))
    conn.commit()
    conn.close()
    session['subscribed'] = True
    return redirect(url_for('home'))

@app.route('/subscribe/cancel')
def subscribe_cancel():
    logger.debug("Accessing subscribe cancel")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))