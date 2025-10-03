# home_routes.py
from flask import render_template, session, redirect, url_for, request
from db import get_db
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('landing'))

def landing():
    return render_template('landing.html.j2')

def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        # Fetch posts with sort
        sort = request.args.get('sort', 'latest')
        if sort == 'latest':
            order_by = 'p.created_at DESC'
        elif sort == 'most_views':
            order_by = 'p.views DESC'
        elif sort == 'most_likes':
            order_by = 'p.likes DESC'
        else:
            order_by = 'p.created_at DESC'
            sort = 'latest'  # fallback

        c.execute(f'''
            SELECT p.*, 
            (SELECT handle FROM posts o WHERE o.id = p.original_post_id) as original_handle,
            (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as likes,
            (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id) as reposts,
            (SELECT 1 FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
            (SELECT 1 FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
            FROM posts p 
            ORDER BY {order_by}
        ''', (session['user_id'], session['user_id']))
        raw_posts = c.fetchall()
        posts = [dict(row) for row in raw_posts]
        
        # Initialize viewed_posts if not set
        if 'viewed_posts' not in session:
            session['viewed_posts'] = []
        
        # Add is_new for highlighting
        viewed_posts = set(session.get('viewed_posts', []))
        for post in posts:
            post['is_new'] = post['id'] not in viewed_posts
        
        # Increment views for new posts
        new_viewed = [post['id'] for post in posts if post['is_new']]
        if new_viewed:
            try:
                placeholders = ','.join(['?' for _ in new_viewed])
                c.execute(f"UPDATE posts SET views = views + 1 WHERE id IN ({placeholders})", new_viewed)
                conn.commit()
                viewed_posts.update(new_viewed)
                session['viewed_posts'] = list(viewed_posts)
                logger.debug(f"Incremented views for posts: {new_viewed}")
            except Exception as e:
                logger.error(f"Failed to increment views for posts {new_viewed}: {str(e)}")
                conn.rollback()
        
        # Fetch comments
        c.execute('SELECT * FROM comments ORDER BY created_at DESC')
        all_comments = [dict(row) for row in c.fetchall()]
        comments = {}
        for comment in all_comments:
            post_id = comment['post_id']
            if post_id not in comments:
                comments[post_id] = []
            comments[post_id].append(comment)
        
        # Fetch assigned lessons (in feed)
        c.execute('''SELECT l.* FROM lessons l 
                     JOIN lessons_users lu ON l.id = lu.lesson_id 
                     LEFT JOIN completed_lessons cl ON l.id = cl.lesson_id AND cl.user_id = lu.user_id
                     WHERE lu.user_id = ? AND cl.id IS NULL''', (session['user_id'],))
        raw_lessons = c.fetchall()
        lessons = []
        for row in raw_lessons:
            lesson = dict(row)
            if lesson['mc_options']:
                try:
                    lesson['mc_options'] = json.loads(lesson['mc_options'])
                except json.JSONDecodeError:
                    lesson['mc_options'] = []
            if lesson['sentence_options']:
                try:
                    lesson['sentence_options'] = json.loads(lesson['sentence_options'])
                except json.JSONDecodeError:
                    lesson['sentence_options'] = []
            lessons.append(lesson)
        
        # Interleave posts and lessons
        combined = []
        lessons_copy = lessons[:]
        for post in posts:
            combined.append({'type': 'post', **post})
            if lessons_copy:
                lesson = lessons_copy.pop(0)
                combined.append({'type': 'lesson', **lesson})
        for remaining_lesson in lessons_copy:
            combined.append({'type': 'lesson', **remaining_lesson})
        
        return render_template('home.html.j2', 
                             posts=posts, 
                             lessons=lessons, 
                             combined=combined, 
                             comments=comments,
                             theme=session.get('theme', 'astronaut'),
                             language=session.get('language', 'en'),
                             sort_option=sort)
    
    except Exception as e:
        logger.error(f"Home route failed: {str(e)}")
        if conn:
            conn.rollback()
        return render_template('error.html.j2', 
                             error=f"Failed to load home page: {str(e)}",
                             theme=session.get('theme', 'astronaut'),
                             language=session.get('language', 'en')), 500
    finally:
        if conn:
            conn.close()