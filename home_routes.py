# home_routes.py (updated)
from flask import session, redirect, url_for, render_template, flash
import logging
import json

logger = logging.getLogger(__name__)

from db import get_db
from utils import filter_content  # Import filter_content from utils.py

def index():
    return redirect(url_for('home'))

def home():
    logger.debug(f"Home route - Session: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session, redirecting to login")
        return redirect(url_for('login'))
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Ensure session has grade and handle (fallback, though set in login)
        if 'grade' not in session or 'handle' not in session:
            c.execute("SELECT grade, handle FROM users WHERE id = ?", (session['user_id'],))
            user = c.fetchone()
            session['grade'] = user['grade'] if user and user['grade'] is not None else 1
            session['handle'] = user['handle'] if user and user['handle'] is not None else session.get('email', 'User')
            logger.debug(f"Set session['grade'] to {session['grade']} and session['handle'] to {session['handle']} for user {session['user_id']}")

        user_id = session.get('user_id')
        grade = session.get('grade', 1)

        # Fetch all posts (no grade filter, no limit to show all)
        c.execute("""
            SELECT * FROM posts 
            ORDER BY created_at DESC
        """)
        posts_rows = c.fetchall()
        posts = []
        comments = {}
        
        # Fetch liked and reposted by current user
        liked_by_user = set()
        reposted_by_user = set()
        if user_id:
            c.execute('SELECT post_id FROM post_likes WHERE user_id = ?', (user_id,))
            liked_by_user = {row['post_id'] for row in c.fetchall()}
            c.execute('SELECT post_id FROM reposts WHERE user_id = ?', (user_id,))
            reposted_by_user = {row['post_id'] for row in c.fetchall()}

        for row in posts_rows:
            post = dict(row)
            post['content'] = filter_content(post['content'] or '')
            post['liked_by_user'] = post['id'] in liked_by_user
            post['reposted_by_user'] = post['id'] in reposted_by_user

            # Fetch comments for this post (full dict, no limit)
            c.execute("""
                SELECT c.*, u.handle 
                FROM comments c 
                JOIN users u ON c.user_id = u.id 
                WHERE c.post_id = ? 
                ORDER BY c.created_at ASC
            """, (row['id'],))
            comments[row['id']] = [dict(r) for r in c.fetchall()]

            posts.append(post)

        # Fetch a random incomplete lesson (add RANDOM for variety, keep grade filter)
        c.execute("""
            SELECT id, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer 
            FROM lessons 
            WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 
            ORDER BY RANDOM() LIMIT 1
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
                            comments=comments,
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

def landing():
    logger.debug("Landing route")
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))