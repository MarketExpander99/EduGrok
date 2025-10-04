# home_routes.py
from flask import render_template, session, redirect, url_for, request, flash
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
        user_id = session['user_id']
        # UPDATED: Get friends' user_ids (approved friendships)
        c.execute('''
            SELECT u.id FROM users u
            WHERE u.id IN (
                SELECT target_id FROM friendships WHERE requester_id = ? AND status = 'approved'
                UNION
                SELECT requester_id FROM friendships WHERE target_id = ? AND status = 'approved'
            )
        ''', (user_id, user_id))
        friend_ids = [row['id'] for row in c.fetchall()]
        friend_ids.append(user_id)  # Include self
        
        # Fetch posts with sort - UPDATED: Filter to friends and self
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

        placeholders = ','.join(['?' for _ in friend_ids])
        c.execute(f'''
            SELECT p.*, 
            (SELECT handle FROM posts o WHERE o.id = p.original_post_id) as original_handle,
            (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as likes,
            (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id) as reposts,
            (SELECT 1 FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
            (SELECT 1 FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
            FROM posts p 
            WHERE p.user_id IN ({placeholders})
            ORDER BY {order_by}
        ''', tuple(friend_ids + [user_id, user_id]))
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
        
        # UPDATED: Fetch only assigned but NOT completed lessons (hide completed from feed)
        c.execute('''SELECT l.*, lu.assigned_at 
                   FROM lessons l 
                   INNER JOIN lessons_users lu ON l.id = lu.lesson_id AND lu.user_id = ? 
                   LEFT JOIN completed_lessons cl ON l.id = cl.lesson_id AND cl.user_id = ? 
                   WHERE cl.completed_at IS NULL 
                   ORDER BY l.id''', (user_id, user_id))
        lessons_data = [dict(row) for row in c.fetchall()]
        lessons = []
        for row in lessons_data:
            if row['mc_options']:
                row['mc_options'] = json.loads(row['mc_options'])
            if row['sentence_options']:
                row['sentence_options'] = json.loads(row['sentence_options'])
            lessons.append(row)
        
        # UPDATED: Fetch friends count
        c.execute('''
            SELECT COUNT(*) as friend_count FROM friendships 
            WHERE (requester_id = ? OR target_id = ?) AND status = 'approved'
        ''', (user_id, user_id))
        friend_count = c.fetchone()['friend_count']
        
        logger.debug(f"Home feed loaded for user {user_id} with {len(posts)} posts and {len(lessons)} lessons")
        return render_template('home.html.j2', 
                             posts=posts, 
                             comments=comments, 
                             lessons=lessons, 
                             sort=sort, 
                             friend_count=friend_count,
                             theme=session.get('theme', 'astronaut'), 
                             language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home route failed: {str(e)}")
        flash('Error loading feed', 'error')
        return render_template('error.html.j2', error="Failed to load home", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500
    finally:
        if conn:
            conn.close()