# app.py
# app.py (updated main file - replace your existing one with this)
import os
import secrets
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory, abort
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse
import mimetypes
from werkzeug.utils import secure_filename

from utils import allowed_file, embed_links  # Import helpers from utils.py

from db import get_db, close_db, init_db, reset_db, check_db_schema, seed_lessons
from auth import register, login, logout, set_theme, set_language

# Import routes from split files
from db_routes import reset_db_route
from home_routes import index, home, landing
from post_routes import create_post, like_post, repost_post, add_comment
from lesson_routes import check_lesson, complete_lesson, reset_lesson, lessons, generate_lesson
from assess_routes import assess, take_test, game
from user_routes import profile, parent_dashboard, update_points, update_coins, beta, feedback
from game_routes import phonics_game

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

@app.teardown_appcontext
def teardown_db(error):
    close_db(error)

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

# Auth routes (already in auth.py, adding rules here)
app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
app.add_url_rule('/logout', 'logout', logout)
app.add_url_rule('/set_theme', 'set_theme', set_theme, methods=['POST'])
app.add_url_rule('/set_language', 'set_language', set_language, methods=['POST'])

# Register routes from other files
app.add_url_rule('/reset_db', 'reset_db_route', reset_db_route)

app.add_url_rule('/', 'index', index)
app.add_url_rule('/home', 'home', home)
app.add_url_rule('/landing', 'landing', landing)

app.add_url_rule('/create_post', 'create_post', create_post, methods=['POST'])
app.add_url_rule('/like/<int:post_id>', 'like_post', like_post, methods=['POST'])
app.add_url_rule('/repost/<int:post_id>', 'repost_post', repost_post, methods=['POST'])
app.add_url_rule('/comment/<int:post_id>', 'add_comment', add_comment, methods=['POST'])

app.add_url_rule('/check_lesson', 'check_lesson', check_lesson, methods=['POST'])
app.add_url_rule('/complete_lesson/<int:lesson_id>', 'complete_lesson', complete_lesson)
app.add_url_rule('/reset_lesson/<int:lesson_id>', 'reset_lesson', reset_lesson)
app.add_url_rule('/lessons', 'lessons', lessons)
app.add_url_rule('/generate_lesson', 'generate_lesson', generate_lesson, methods=['POST'])

app.add_url_rule('/assess', 'assess', assess, methods=['GET', 'POST'])
app.add_url_rule('/test', 'take_test', take_test, methods=['GET', 'POST'])
app.add_url_rule('/game', 'game', game)

app.add_url_rule('/profile', 'profile', profile)
app.add_url_rule('/parent_dashboard', 'parent_dashboard', parent_dashboard)
app.add_url_rule('/update_points', 'update_points', update_points, methods=['POST'])
app.add_url_rule('/update_coins', 'update_coins', update_coins, methods=['POST'])
app.add_url_rule('/beta', 'beta', beta, methods=['GET', 'POST'])
app.add_url_rule('/feedback', 'feedback', feedback, methods=['GET', 'POST'])

app.add_url_rule('/phonics_game', 'phonics_game', phonics_game, methods=['GET', 'POST'])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')