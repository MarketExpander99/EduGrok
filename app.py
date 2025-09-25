import os
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory, abort
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import re
from datetime import datetime
from db import get_db, close_db, init_db, reset_db, check_db_schema, seed_lessons
from auth import register, login, logout, set_theme, set_language
from urllib.parse import urlparse
import mimetypes
import json
from werkzeug.utils import secure_filename

# Load .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Secure session settings
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Configure logging
handler = RotatingFileHandler('/tmp/app.log', maxBytes=10000, backupCount=1)
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

# Helper functions for media
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'mp4'}

def embed_links(content):
    # YouTube
    youtube_regex = r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
    match = re.search(youtube_regex, content)
    if match:
        video_id = match.group(1)
        embed = f'<iframe width="300" height="200" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
        content = re.sub(youtube_regex, embed, content, count=1)
    
    # Rumble
    rumble_regex = r'https?://rumble\.com/v([a-zA-Z0-9_-]+)'
    match = re.search(rumble_regex, content)
    if match:
        video_id = match.group(1)
        embed = f'<iframe width="300" height="200" src="https://rumble.com/embed/{video_id}/" frameborder="0" allowfullscreen></iframe>'
        content = re.sub(rumble_regex, embed, content, count=1)
    
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

# Auth routes
app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
app.add_url_rule('/logout', 'logout', logout)
app.add_url_rule('/set_theme', 'set_theme', set_theme, methods=['POST'])
app.add_url_rule('/set_language', 'set_language', set_language, methods=['POST'])

# Static file route to ensure CSS serves
@app.route('/static/<path:filename>')
def serve_static(filename):
    # Strip query params from filename (e.g., 'styles.css?v=1' -> 'styles.css')
    parsed = urlparse(request.path)
    clean_filename = os.path.basename(parsed.path)  # Grabs just the file, ignores query
    
    try:
        # Ensure static dir exists
        static_dir = app.static_folder
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
        
        # Guess MIME type
        mime_type, _ = mimetypes.guess_type(clean_filename)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        response = send_from_directory(static_dir, clean_filename)
        response.headers['Content-Type'] = mime_type
        
        logger.debug(f"Serving static file: {clean_filename} (from req: {filename}, MIME: {mime_type})")
        return response
    except FileNotFoundError:
        logger.debug(f"Static file not found: {clean_filename}")
        abort(404)
    except Exception as e:
        logger.error(f"Static serve error for {clean_filename}: {e}")
        abort(500)

# Initialize app
def init_app():
    with app.app_context():
        try:
            init_db()
            check_db_schema()
            seed_lessons()
            # Setup upload folder
            upload_folder = os.path.join(app.static_folder, 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            app.config['UPLOAD_FOLDER'] = upload_folder
            app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit
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
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    logger.debug(f"Home route - Session: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session, redirecting to login")
        return redirect(url_for('login'))
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Ensure session has grade
        if 'grade' not in session:
            c.execute("SELECT grade, handle FROM users WHERE id = ?", (session['user_id'],))
            user = c.fetchone()
            session['grade'] = user['grade'] if user and user['grade'] is not None else 1
            session['handle'] = user['handle'] if user and user['handle'] is not None else 'User'
            logger.debug(f"Set session['grade'] to {session['grade']} and session['handle'] to {session['handle']} for user {session['user_id']}")

        user_id = session.get('user_id')
        grade = session.get('grade', 1)

        # Fetch posts (updated to include media_url, views, and reposts)
        c.execute("""
            SELECT p.id, p.content, p.subject, p.grade, p.likes, p.handle, p.created_at, p.media_url, p.views, p.reposts
            FROM posts p 
            WHERE p.grade = ? 
            ORDER BY p.created_at DESC LIMIT 5
        """, (grade,))
        posts_data = c.fetchall()
        posts = []
        comments_data = {}
        for row in posts_data:
            post = {
                'id': row['id'],
                'content': filter_content(row['content'] or ''),
                'subject': row['subject'] or 'General',
                'grade': row['grade'] or 1,
                'likes': row['likes'] or 0,
                'handle': row['handle'] or 'Unknown',
                'created_at': row['created_at'] or 'Unknown',
                'media_url': row['media_url'] or None,
                'views': row['views'] or 0,
                'reposts': row['reposts'] or 0
            }
            c.execute("SELECT 1 FROM post_likes WHERE user_id = ? AND post_id = ?", (user_id, row['id']))
            post['liked_by_user'] = c.fetchone() is not None

            # Fetch comments for this post
            c.execute("""
                SELECT c.content, u.handle, c.created_at 
                FROM comments c 
                JOIN users u ON c.user_id = u.id 
                WHERE c.post_id = ? 
                ORDER BY c.created_at ASC 
                LIMIT 5
            """, (row['id'],))
            comments_data[row['id']] = [
                {'content': filter_content(r[0] or ''), 'handle': r[1] or 'Unknown', 'created_at': r[2] or 'Unknown'}
                for r in c.fetchall()
            ]

            posts.append(post)

        # Fetch lesson
        c.execute("""
            SELECT id, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer 
            FROM lessons 
            WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 
            LIMIT 1
        """, (user_id, grade))
        lesson_result = c.fetchone()
        lesson = dict(lesson_result) if lesson_result else None
        if lesson and lesson['mc_options']:
            lesson['mc_options'] = json.loads(lesson['mc_options'])

        # Fetch test
        c.execute("""
            SELECT id, grade, score, date 
            FROM tests 
            WHERE user_id = ? 
            ORDER BY date DESC LIMIT 1
        """, (user_id,))
        test_result = c.fetchone()
        test = dict(test_result) if test_result else None

        # Fetch subscription status
        c.execute("SELECT subscribed FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        subscribed = result['subscribed'] if result else 0

        logger.info(f"User {user_id} accessed home with {len(posts)} posts")
        return render_template('home.html.j2', 
                            posts=posts, 
                            comments=comments_data,
                            lesson=lesson, 
                            test=test, 
                            subscribed=subscribed, 
                            theme=session.get('theme', 'astronaut'), 
                            language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home route failed: {str(e)}")
        flash('Failed to load homepage. Try again or reset DB.', 'error')
        return render_template('error.html.j2', 
                            error=f"Failed to load homepage: {str(e)}", 
                            theme=session.get('theme', 'astronaut'), 
                            language=session.get('language', 'en')), 500

@app.route('/landing')
def landing():
    logger.debug("Landing route")
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/create_post', methods=['POST'])
def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    content = filter_content(request.form.get('content', ''))
    subject = request.form.get('subject', 'General')
    if not content:
        flash('Post content is required', 'error')
        return redirect(url_for('home'))
    
    media_url = None
    if 'media' in request.files:
        file = request.files['media']
        if file.filename != '':
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                media_url = f"/static/uploads/{filename}"
    
    # Handle external links
    content = embed_links(content)
    
    try:
        conn = get_db()
        user_id = session.get('user_id')
        handle = session.get('handle', 'User')
        grade = session.get('grade', 1)
        conn.execute('INSERT INTO posts (user_id, handle, content, subject, grade, created_at, media_url, views, reposts) VALUES (?, ?, ?, ?, ?, datetime("now"), ?, 0, 0)',
                     (user_id, handle, content, subject, grade, media_url))
        conn.commit()
        flash('Post created successfully', 'success')
        logger.info(f"User {user_id} created post: {content[:50]}...")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('home'))

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM post_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Already liked'}), 400
        c.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, session['user_id']))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
        logger.info(f"User {session['user_id']} liked post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Like post failed: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/repost/<int:post_id>', methods=['POST'])
def repost_post(post_id):
    logger.debug(f"Reposting post {post_id}")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM reposts WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Already reposted'}), 400
        c.execute("INSERT INTO reposts (user_id, post_id, created_at) VALUES (?, ?, datetime('now'))", (session['user_id'], post_id))
        c.execute("UPDATE posts SET reposts = reposts + 1 WHERE id = ?", (post_id,))
        conn.commit()
        logger.info(f"User {session['user_id']} reposted post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Repost failed: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    logger.debug(f"Adding comment to post {post_id}")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    content = request.form.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'error': 'Comment cannot be empty'}), 400
    content = filter_content(content)
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, datetime('now'))",
                  (post_id, session['user_id'], content))
        conn.commit()
        logger.info(f"User {session['user_id']} commented on post {post_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Comment failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('home'))

@app.route('/check_lesson', methods=['POST'])
def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    
    try:
        conn = get_db()
        c = conn.cursor()
        # Get lesson details
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson = dict(c.fetchone())
        
        is_correct = 0
        points_award = 0
        if activity_type == 'math_fill':
            expected = eval(lesson.get('mc_answer', '0'))  # e.g., '6*3' -> 18
            is_correct = 1 if int(response) == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'spelling_complete':
            expected = lesson.get('mc_answer', '').lower()
            is_correct = 1 if response.lower().strip() == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'mc_choice':
            expected = lesson.get('mc_answer', '')
            is_correct = 1 if response == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'sentence_complete':
            expected = lesson.get('mc_answer', '')
            is_correct = 1 if response.lower() in expected.lower() else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'match_three':
            expected_matches = 3
            user_matches = len([m for m in json.loads(response) if m in json.loads(lesson.get('mc_options', '[]'))])
            is_correct = 1 if user_matches >= expected_matches else 0
            points_award = 10 if is_correct else 5
        
        # Store response
        c.execute("""
            INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, submitted_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (lesson_id, session['user_id'], activity_type, response, is_correct))
        
        # Mark lesson completed and award points if flagged
        if data.get('complete_lesson', False):
            c.execute("UPDATE lessons SET completed = 1 WHERE id = ?", (lesson_id,))
            c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", 
                      (session['user_id'], session['user_id'], points_award))
            c.execute("UPDATE users SET star_coins = star_coins + ? WHERE id = ?", (points_award, session['user_id']))
        
        conn.commit()
        return jsonify({'success': True, 'is_correct': bool(is_correct), 'points': points_award})
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

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
            flash('Assessment completed', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Assess failed: {str(e)}")
            conn.rollback()
            flash('Server error', 'error')
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
        {"q": "Example Q10", "a": ["Example10", "Wrong", "Wrong"], "correct": "Example10"}
    ]
    return render_template('assess.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/complete_lesson/<int:lesson_id>')
def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
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
        conn.commit()
        flash('Lesson completed', 'success')
        logger.info(f"User {session['user_id']} completed lesson {lesson_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

@app.route('/reset_lesson/<int:lesson_id>')
def reset_lesson(lesson_id):
    logger.debug(f"Resetting lesson {lesson_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 0 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        conn.commit()
        flash('Lesson reset for retry', 'success')
        logger.info(f"User {session['user_id']} reset lesson {lesson_id}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

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
            flash('Test completed', 'success')
            return redirect(url_for('game', score=score))
        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
            conn.rollback()
            flash('Server error', 'error')
            return render_template('test.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        {"q": "Example Q2", "a": ["Example2", "Wrong", "Wrong"], "correct": "Example2"},
        {"q": "Example Q3", "a": ["Example3", "Wrong", "Wrong"], "correct": "Example3"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"}
    ]
    return render_template('test.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/game')
def game():
    logger.debug("Game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    score = int(request.args.get('score', 0))
    difficulty = 'easy' if score < 3 else 'hard'
    logger.info(f"User {session['user_id']} accessed game with difficulty {difficulty}")
    return render_template('game.html.j2', difficulty=difficulty, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'), score=score)

@app.route('/profile')
def profile():
    logger.debug("Profile route")
    if 'user_id' not in session:
        logger.debug("No user_id in session, redirecting to login")
        flash('Login required', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        if not user:
            logger.error(f"No user found for user_id {session['user_id']}")
            flash('User not found. Please log in again.', 'error')
            session.pop('user_id', None)
            return redirect(url_for('login'))
        
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND completed = 1 AND grade = ?", (session['user_id'], session['grade']))
        lessons_completed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ?", (session['user_id'], session['grade']))
        total_lessons = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM games WHERE user_id = ?", (session['user_id'],))
        games_played = c.fetchone()[0]
        c.execute("SELECT AVG(score) FROM tests WHERE user_id = ?", (session['user_id'],))
        avg_score = round(c.fetchone()[0] or 0, 1)
        c.execute("SELECT points FROM user_points WHERE user_id = ?", (session['user_id'],))
        result = c.fetchone()
        points = result['points'] if result else 0
        c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (session['user_id'],))
        badges = [dict(row) for row in c.fetchall()]
        c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (session['user_id'],))
        feedbacks = [dict(row) for row in c.fetchall()]
        logger.info(f"User {session['user_id']} accessed profile")
        return render_template('profile.html.j2', 
                              user=user,
                              lessons_completed=f"{lessons_completed}/{total_lessons}",
                              games_played=games_played,
                              avg_score=avg_score,
                              grade=session.get('grade', 1),
                              theme=session.get('theme', 'astronaut'),
                              language=session.get('language', 'en'),
                              points=points,
                              star_coins=user['star_coins'] if user['star_coins'] is not None else 0,
                              badges=badges,
                              feedbacks=feedbacks)
    except Exception as e:
        logger.error(f"Profile route failed: {str(e)}")
        flash('Failed to load profile. Try logging in again.', 'error')
        return render_template('error.html.j2', 
                              error=f"Failed to load profile: {str(e)}", 
                              theme=session.get('theme', 'astronaut'), 
                              language=session.get('language', 'en')), 500

@app.route('/parent_dashboard')
def parent_dashboard():
    logger.debug("Parent dashboard route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
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
        logger.info(f"User {session['user_id']} accessed parent dashboard")
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
        c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 ORDER BY id", (session['user_id'], session['grade']))
        lessons_data = c.fetchall()
        lessons_list = [dict(row) for row in lessons_data]
        if not lessons_list:
            logger.warning(f"No lessons found for user {session['user_id']} and grade {session['grade']}")
            seed_lessons()
            c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 ORDER BY id", (session['user_id'], session['grade']))
            lessons_list = [dict(row) for row in c.fetchall()]
        logger.info(f"Retrieved {len(lessons_list)} lessons for user {session['user_id']}")
        return render_template('lessons.html.j2', lessons=lessons_list, grade=session['grade'], theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Lessons route failed: {str(e)}")
        return render_template('error.html.j2', error=f"Failed to load lessons: {str(e)}", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

@app.route('/update_points', methods=['POST'])
def update_points():
    logger.debug("Update points route")
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

@app.route('/update_coins', methods=['POST'])
def update_coins():
    logger.debug("Update coins route")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json()
    coins = int(data.get('coins', 0))
    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT star_coins FROM users WHERE id = ?", (user_id,))
        current_coins = c.fetchone()['star_coins'] or 0
        if current_coins + coins < 0:
            return jsonify({'success': False, 'error': 'Not enough coins'}), 400
        c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (coins, user_id))
        if coins == -10:
            c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, ?, ?)", 
                      (user_id, 'Coin Redeemer', datetime.now().isoformat()))
        conn.commit()
        logger.info(f"Updated {coins} Star Coins for user {user_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coins: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/phonics_game', methods=['GET', 'POST'])
def phonics_game():
    logger.debug("Phonics game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        grade = session.get('grade', 1)
        language = session.get('language', 'en')
        # Define phonics word lists by grade
        word_lists = {
            1: {
                'en': [
                    {'word': 'cat', 'sound': '/kæt/'},
                    {'word': 'dog', 'sound': '/dɒɡ/'},
                    {'word': 'sun', 'sound': '/sʌn/'},
                    {'word': 'moon', 'sound': '/muːn/'}
                ],
                'bilingual': [
                    {'word': 'cat', 'sound': '/kæt/', 'af': 'kat', 'af_sound': '/kat/'},
                    {'word': 'dog', 'sound': '/dɒɡ/', 'af': 'hond', 'af_sound': '/ɦɔnt/'},
                    {'word': 'sun', 'sound': '/sʌn/', 'af': 'son', 'af_sound': '/sɔn/'},
                    {'word': 'moon', 'sound': '/muːn/', 'af': 'maan', 'af_sound': '/mɑːn/'}
                ]
            },
            2: {
                'en': [
                    {'word': 'ship', 'sound': '/ʃɪp/'},
                    {'word': 'fish', 'sound': '/fɪʃ/'},
                    {'word': 'tree', 'sound': '/triː/'},
                    {'word': 'bird', 'sound': '/bɜːrd/'}
                ],
                'bilingual': [
                    {'word': 'ship', 'sound': '/ʃɪp/', 'af': 'skip', 'af_sound': '/skɪp/'},
                    {'word': 'fish', 'sound': '/fɪʃ/', 'af': 'vis', 'af_sound': '/fɪs/'},
                    {'word': 'tree', 'sound': '/triː/', 'af': 'boom', 'af_sound': '/bʊəm/'},
                    {'word': 'bird', 'sound': '/bɜːrd/', 'af': 'voël', 'af_sound': '/fuəl/'}
                ]
            },
            3: {
                'en': [
                    {'word': 'house', 'sound': '/haʊs/'},
                    {'word': 'cloud', 'sound': '/klaʊd/'},
                    {'word': 'spoon', 'sound': '/spuːn/'},
                    {'word': 'train', 'sound': '/treɪn/'}
                ],
                'bilingual': [
                    {'word': 'house', 'sound': '/haʊs/', 'af': 'huis', 'af_sound': '/ɦœɪs/'},
                    {'word': 'cloud', 'sound': '/klaʊd/', 'af': 'wolk', 'af_sound': '/vɔlk/'},
                    {'word': 'spoon', 'sound': '/spuːn/', 'af': 'lepel', 'af_sound': '/lɪəpəl/'},
                    {'word': 'train', 'sound': '/treɪn/', 'af': 'trein', 'af_sound': '/trɛɪn/'}
                ]
            }
        }
        timer_duration = 60 if grade == 1 else 45 if grade == 2 else 30
        words = word_lists[grade][language]

        if request.method == 'POST':
            score = int(request.get_json().get('score', 0))
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO games (user_id, score) VALUES (?, ?)", (session['user_id'], score))
            c.execute("SELECT COUNT(*) FROM games WHERE user_id = ?", (session['user_id'],))
            game_count = c.fetchone()[0]
            if game_count >= 5:
                c.execute("INSERT OR IGNORE INTO badges (user_id, badge_name, awarded_date) VALUES (?, ?, ?)", 
                         (session['user_id'], 'Phonics Pro', datetime.now().isoformat()))
            conn.commit()
            logger.info(f"User {session['user_id']} completed phonics game with score {score}")
            return jsonify({'success': True})

        logger.info(f"User {session['user_id']} accessed phonics game, grade {grade}, language {language}")
        return render_template('phonics_game.html.j2', 
                             theme=session.get('theme', 'astronaut'), 
                             grade=grade, 
                             language=language, 
                             words=words, 
                             timer_duration=timer_duration)
    except Exception as e:
        logger.error(f"Phonics game failed: {str(e)}")
        return render_template('error.html.j2', error=f"Failed to load phonics game: {str(e)}", 
                             theme=session.get('theme', 'astronaut'), 
                             language=session.get('language', 'en')), 500

@app.route('/generate_lesson', methods=['POST'])
def generate_lesson():
    logger.debug("Generate lesson route")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    grade = request.form.get('grade')
    subject = request.form.get('subject')
    if not grade or not subject or not grade.isdigit() or int(grade) not in [1, 2, 3]:
        logger.error("Invalid grade or subject")
        flash('Invalid grade (1-3) or subject', 'error')
        return redirect(url_for('lessons'))
    try:
        lesson_content = f"Generated {subject} lesson for Grade {grade}"
        trace_word = None
        sound = None
        spell_word = None
        mc_question = None
        mc_options = None
        mc_answer = None
        if subject == 'language':
            word_lists = {
                1: {'word': 'cat', 'sound': '/kæt/'},
                2: {'word': 'ship', 'sound': '/ʃɪp/'},
                3: {'word': 'house', 'sound': '/haʊs/'}
            }
            trace_word = word_lists[int(grade)]['word']
            sound = word_lists[int(grade)]['sound']
            spell_word = trace_word
            mc_question = 'What is the correct spelling?'
            mc_options = f'["{trace_word}", "{trace_word[0]}a{trace_word[1:]}", "{trace_word[:2]}", "{trace_word}a"]'
            mc_answer = trace_word
        elif subject == 'math':
            if int(grade) == 1:
                lesson_content = 'What is 6 + 3? <input type="number" id="math-input" placeholder="Enter answer"> <button onclick="checkMath()">Check</button>'
                mc_answer = '9'
            elif int(grade) == 2:
                lesson_content = 'Match: 2x3=6, 4x2=8, 5x1=5 <div id="match-game"><!-- JS drag-drop --></div>'
                mc_options = '["6", "8", "5"]'
                mc_answer = '6'
            elif int(grade) == 3:
                lesson_content = '6 x 3 = ? <input type="number" id="math-input" placeholder="Enter answer"> <button onclick="checkMath()">Check</button>'
                mc_answer = '18'
        if session.get('language') == 'bilingual':
            lesson_content += f"<br>Afrikaans: Gegenereerde {subject} les vir Graad {grade}"
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO lessons (user_id, grade, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session['user_id'], grade, subject, lesson_content, 0, trace_word, sound, spell_word, mc_question, mc_options, mc_answer))
        conn.commit()
        logger.info(f"Generated lesson for user {session['user_id']}: {subject}")
        flash('Lesson generated', 'success')
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

@app.route('/beta', methods=['GET', 'POST'])
def beta():
    logger.debug("Beta route")
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            logger.info(f"Beta invite requested: {email}")
            flash('Thanks! You\'re on the beta list. Check your email soon.', 'success')
        return redirect(url_for('landing'))
    return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    logger.debug("Feedback route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            rating = int(request.form.get('rating', 0))
            comments = filter_content(request.form.get('comments', ''))
            if not 1 <= rating <= 5:
                flash('Rating must be between 1 and 5', 'error')
                return redirect(url_for('feedback'))
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO feedback (user_id, rating, comments, submitted_date) VALUES (?, ?, ?, ?)",
                     (session['user_id'], rating, comments, datetime.now().isoformat()))
            conn.commit()
            flash('Feedback submitted', 'success')
            logger.info(f"User {session['user_id']} submitted feedback: rating={rating}")
            return redirect(url_for('profile'))
        except Exception as e:
            logger.error(f"Feedback submission failed: {str(e)}")
            conn.rollback()
            flash('Server error', 'error')
            return redirect(url_for('feedback'))
    return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')