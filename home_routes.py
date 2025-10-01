# home_routes.py
from flask import render_template, session, redirect, url_for
from db import get_db
import json
import logging

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
    conn = get_db()
    c = conn.cursor()
    # FIXED: Updated query to use subquery for original_handle from posts table
    c.execute('''
        SELECT p.*, 
        (SELECT handle FROM posts o WHERE o.id = p.original_post_id) as original_handle,
        (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as likes,
        (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id) as reposts,
        (SELECT 1 FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
        (SELECT 1 FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
        FROM posts p 
        ORDER BY p.created_at DESC
    ''', (session['user_id'], session['user_id']))
    posts = [dict(row) for row in c.fetchall()]
    
    # FIXED: Increment views for new/unviewed posts (simple session-based tracking)
    viewed_posts = set(session.get('viewed_posts', []))
    new_viewed = [post['id'] for post in posts if post['id'] not in viewed_posts]
    if new_viewed:
        placeholders = ','.join(['?' for _ in new_viewed])
        c.execute(f"UPDATE posts SET views = views + 1 WHERE id IN ({placeholders})", new_viewed)
        conn.commit()
        viewed_posts.update(new_viewed)
        session['viewed_posts'] = list(viewed_posts)
        logger.debug(f"Incremented views for posts: {new_viewed}")
    
    # Fetch comments
    c.execute('SELECT * FROM comments ORDER BY created_at DESC')
    all_comments = [dict(row) for row in c.fetchall()]
    comments = {}
    for comment in all_comments:
        post_id = comment['post_id']
        if post_id not in comments:
            comments[post_id] = []
        comments[post_id].append(comment)
    # Fetch lessons, process content if needed
    c.execute('SELECT * FROM lessons')
    raw_lessons = c.fetchall()
    lessons = []
    for row in raw_lessons:
        lesson = dict(row)
        if lesson['type'] == 'multiple_choice':
            try:
                lesson['content'] = json.loads(lesson['content'])
            except json.JSONDecodeError:
                lesson['content'] = {'question': 'Error loading question', 'options': []}
        lessons.append(lesson)
    theme = session.get('theme', 'astronaut')
    language = session.get('language', 'en')
    logger.info(f"Home loaded for user {session['user_id']}")
    return render_template('home.html.j2', posts=posts, comments=comments, lessons=lessons, theme=theme, language=language)