import os
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import re
import requests
from datetime import datetime
# import stripe  # Commented out until launch
from db import get_db, close_db, init_db, reset_db, check_db_schema, seed_lessons
from auth import register, login, logout, set_theme, set_language

# Load .env file
load_dotenv()

# Stripe setup - commented out until launch
# stripe.api_key = os.environ.get('STRIPE_KEY')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Secure session settings
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

@app.teardown_appcontext
def teardown_db(error):
    close_db(error)

@app.route('/reset_db')
def reset_db_route():
    if 'user_id' not in session:
        logger.error("Unauthorized access to /reset_db")
        return "Login required", 401
    reset_db()
    return redirect(url_for('home'))

# Explicitly register auth routes
app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
app.add_url_rule('/logout', 'logout', logout)
app.add_url_rule('/set_theme', 'set_theme', set_theme, methods=['POST'])
app.add_url_rule('/set_language', 'set_language', set_language, methods=['POST'])

# Initialize app
def init_app():
    with app.app_context():
        try:
            init_db()
            check_db_schema()
            seed_lessons()
            logger.info("App initialized - DB ready")
            print("App initialized - DB ready")
        except Exception as e:
            logger.error(f"App init failed: {str(e)}")
            print(f"App init failed: {e}")
            raise

try:
    init_app()
except Exception as e:
    logger.critical(f"Failed to initialize app: {str(e)}")
    raise

@app.route('/')
def home():
    logger.debug(f"Home route - Session: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session, redirecting to login")
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT p.id, p.content, p.subject, p.likes, u.handle, p.reported FROM posts p JOIN users u ON p.user_id = u.id WHERE p.reported = 0 ORDER BY p.id DESC LIMIT 5")
        posts_data = c.fetchall()
        if posts_data is None:
            logger.warning("posts_data is None in home route")
            posts_data = []
        posts = []
        user_id = session.get('user_id')
        for row in posts_data:
            post = dict(
                id=row['id'],
                content=filter_content(row['content']),
                subject=row['subject'],
                likes=row['likes'] or 0,
                handle=row['handle'],
                reported=row['reported']
            )
            if user_id:
                c.execute("SELECT 1 FROM user_likes WHERE user_id = ? AND post_id = ?", (user_id, row['id']))
                like_result = c.fetchone()
                post['liked_by_user'] = like_result is not None
            else:
                post['liked_by_user'] = False
            posts.append(post)
        c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 LIMIT 1", (session['user_id'], session.get('grade', 1)))
        lesson_result = c.fetchone()
        lesson = dict(lesson_result) if lesson_result else None
        c.execute("SELECT id, grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (session['user_id'],))
        test_result = c.fetchone()
        test = dict(test_result) if test_result else None
        return render_template('home.html.j2', posts=posts, lesson=lesson, test=test, subscribed=False, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home route failed: {str(e)}")
        raise

@app.route('/landing')
def landing():
    logger.debug("Landing route")
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/post', methods=['POST'])
def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        return render_template('login.html.j2', error="Unauthorized", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    content = filter_content(request.form.get('content', ''))
    subject = request.form.get('subject', '')
    if not content or not subject:
        return render_template('home.html.j2', error="Content and subject required", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (session['user_id'], content, subject))
        conn.commit()
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {str(e)}")
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
        logger.error(f"Like post failed: {str(e)}")
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
        logger.error(f"Report post failed: {str(e)}")
        conn.rollback()
        return render_template('home.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/assess', methods=['GET', 'POST'])
def assess():
    logger.debug("Assess route")
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
            logger.error(f"Assess failed: {str(e)}")
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
        c.execute("SELECT COUNT(*) FROM badges WHERE user_id = ? AND badge_name = 'Lesson Master'", (session['user_id'],))
        if c.fetchone()[0] == 0:
            c.execute("SELECT COUNT(*) FROM lessons WHERE user_id = ? AND completed = 1", (session['user_id'],))
            if c.fetchone()[0] >= 5:
                c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, 'Lesson Master', ?)", (session['user_id'], datetime.now().isoformat()))
                requests.post('https://www.google-analytics.com/mp/collect', json={
                    'client_id': str(session['user_id']),
                    'events': [{'name': 'badge_earned', 'params': {'badge_name': 'Lesson Master'}}]
                }, params={'measurement_id': 'YOUR_GA_MEASUREMENT_ID', 'api_secret': 'YOUR_GA_API_SECRET'})
        conn.commit()
        requests.post('https://www.google-analytics.com/mp/collect', json={
            'client_id': str(session['user_id']),
            'events': [{'name': 'lesson_completed', 'params': {'lesson_id': lesson_id}}]
        }, params={'measurement_id': 'YOUR_GA_MEASUREMENT_ID', 'api_secret': 'YOUR_GA_API_SECRET'})
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        conn.rollback()
        return render_template('lessons.html.j2', error="Server error", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/test', methods=['GET', 'POST'])
def take_test():
    logger.debug("Test route")
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
            requests.post('https://www.google-analytics.com/mp/collect', json={
                'client_id': str(session['user_id']),
                'events': [{'name': 'test_completed', 'params': {'score': score}}]
            }, params={'measurement_id': 'YOUR_GA_MEASUREMENT_ID', 'api_secret': 'YOUR_GA_API_SECRET'})
            return redirect(url_for('game', score=score))
        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
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
    logger.debug("Game route")
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
        logger.error(f"Profile failed: {str(e)} - Session: {session}")
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
        logger.error(f"Parent dashboard failed: {str(e)}")
        return render_template('error.html.j2', error="Failed to load dashboard.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.route('/lessons')
def lessons():
    logger.debug("Lessons route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? ORDER BY completed", (session['user_id'], session['grade']))
        lessons_data = c.fetchall()
        if lessons_data is None:
            logger.warning("lessons_data is None in lessons route")
            lessons_data = []
        lessons_list = [dict(row) for row in lessons_data]
        return render_template('lessons.html.j2', lessons=lessons_list, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Lessons route failed: {str(e)}")
        return render_template('error.html.j2', error="Failed to load lessons.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

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
        logger.error(f"Update points failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/phonics_game')
def phonics_game():
    logger.debug("Phonics game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('phonics_game.html.j2', theme=session.get('theme', 'astronaut'), grade=session.get('grade', 1), language=session.get('language', 'en'))

@app.route('/generate_lesson', methods=['POST'])
def generate_lesson():
    logger.debug("Generate lesson route")
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
        logger.error(f"API call failed: {str(e)}")
        return render_template('lessons.html.j2', error="Failed to generate lesson - check API", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
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

@app.route('/feedback', methods=['POST'])
def feedback():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        rating = int(request.form.get('rating', 0))
        comments = request.form.get('comments', '')
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': 'Invalid rating'}), 400
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO feedback (user_id, rating, comments, submitted_date) VALUES (?, ?, ?, ?)", 
                  (session['user_id'], rating, comments, datetime.now().isoformat()))
        conn.commit()
        logger.info(f"Feedback submitted by user {session['user_id']}: rating={rating}")
        flash('Thanks for your feedback!', 'success')
        return redirect(url_for('profile'))
    except Exception as e:
        logger.error(f"Feedback failed: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

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
        requests.post('https://www.google-analytics.com/mp/collect', json={
            'client_id': str(session['user_id']),
            'events': [{'name': 'badge_earned', 'params': {'badge_name': badge_name}}]
        }, params={'measurement_id': 'YOUR_GA_MEASUREMENT_ID', 'api_secret': 'YOUR_GA_API_SECRET'})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Award badge failed: {str(e)}")
        return jsonify({'success': False}), 500

# @app.route('/subscribe', methods=['GET', 'POST'])
# def subscribe():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#     if request.method == 'POST':
#         try:
#             session = stripe.checkout.Session.create(
#                 payment_method_types=['card'],
#                 line_items=[{
#                     'price_data': {
#                         'currency': 'zar',
#                         'product_data': {'name': 'EduGrok Premium'},
#                         'unit_amount': 7900,
#                     },
#                     'quantity': 1,
#                 }],
#                 mode='subscription',
#                 success_url=url_for('home', _external=True),
#                 cancel_url=url_for('parent_dashboard', _external=True),
#             )
#             return redirect(session.url, code=303)
#         except Exception as e:
#             logger.error(f"Stripe checkout failed: {e}")
#             flash('Subscription failed. Try again.', 'error')
#             return redirect(url_for('parent_dashboard'))
#     return render_template('subscribe.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)} - {request.url} - Session: {session}")
    print(f"Internal error: {error}")
    return render_template('error.html.j2', error=f"Server error: {str(error)}", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404: {request.url} - Session: {session}")
    print(f"404: {request.url}")
    return render_template('error.html.j2', error="Page not found.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 404

@app.before_request
def log_request():
    logger.debug(f"Request: {request.method} {request.url} - User ID: {session.get('user_id', 'None')} - Session: {session}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))