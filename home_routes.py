from flask import session, redirect, url_for, render_template, flash, request
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

from db import get_db

def filter_content(content):  # Assuming this is defined in app.py, but if needed, duplicate or import
    # ... (copy the filter_content function if not importing)
    pass

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

def landing():
    logger.debug("Landing route")
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))