# home_routes.py (updated: Added update to last_feed_view in home() function)
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
        # NEW: Update last_feed_view on home access
        now = datetime.now().isoformat()
        c.execute("UPDATE users SET last_feed_view = ? WHERE id = ?", (now, user_id))
        conn.commit()
        # FIXED: Removed friends filter to show all posts from all users
        # Keep friends query only for friend_count
        c.execute('''
            SELECT u.id FROM users u
            WHERE u.id IN (
                SELECT target_id FROM friendships WHERE requester_id = ? AND status = 'approved'
                UNION
                SELECT requester_id FROM friendships WHERE target_id = ? AND status = 'approved'
            )
        ''', (user_id, user_id))
        friend_ids = [row['id'] for row in c.fetchall()]
        # No longer using friend_ids for posts filter
        
        # Fetch posts with sort - FIXED: No filter to friends, show all posts
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
            SELECT p.*, u.handle,
            CASE WHEN pl.user_id = {user_id} THEN 1 ELSE 0 END as liked_by_user,
            CASE WHEN pr.user_id = {user_id} THEN 1 ELSE 0 END as reposted_by_user
            FROM posts p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN likes pl ON pl.post_id = p.id AND pl.user_id = {user_id}
            LEFT JOIN reposts pr ON pr.post_id = p.id AND pr.user_id = {user_id}
            ORDER BY {order_by}
            LIMIT 20
        ''')
        posts = c.fetchall()
        
        # Fetch comments for each post
        comments = {}
        for post in posts:
            c.execute("SELECT c.*, u.handle FROM comments c JOIN users u ON c.user_id = u.id WHERE post_id = ? ORDER BY c.created_at ASC", (post['id'],))
            comments[post['id']] = c.fetchall()
        
        # Increment views for each post
        for post in posts:
            c.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post['id'],))
        conn.commit()
        
        # Fetch user data for profile
        c.execute("SELECT handle, grade, star_coins, points FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        session['handle'] = user['handle'] or session.get('email', 'User')
        
        # Fetch recent test
        c.execute("SELECT grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
        recent_test = c.fetchone()
        
        # Fetch lessons completed count
        c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ?", (user_id,))
        lessons_completed = c.fetchone()['count']
        
        # Fetch games played count
        c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (user_id,))
        games_played = c.fetchone()['count']
        
        # Fetch average test score
        c.execute("SELECT AVG(score) as avg FROM tests WHERE user_id = ?", (user_id,))
        avg_result = c.fetchone()
        avg_score = round(avg_result['avg'], 1) if avg_result['avg'] else 'N/A'
        
        # Fetch badges
        c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (user_id,))
        badges = c.fetchall()
        
        # Fetch feedbacks
        c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (user_id,))
        feedbacks = c.fetchall()
        
        return render_template('home.html.j2', 
                               posts=posts, 
                               comments=comments, 
                               user=user, 
                               recent_test=recent_test,
                               lessons_completed=lessons_completed,
                               games_played=games_played,
                               avg_score=avg_score,
                               badges=badges,
                               feedbacks=feedbacks,
                               friend_count=len(friend_ids),
                               sort=sort,
                               theme=session.get('theme', 'astronaut'),
                               language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home route error: {str(e)}")
        if conn:
            conn.rollback()
        flash('Error loading feed', 'error')
        return redirect(url_for('landing'))
    finally:
        if conn:
            conn.close()