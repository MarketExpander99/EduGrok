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
    return render_template('landing.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = None
    feed_lessons = []
    completed_lessons = []
    posts = []
    comments = {}
    try:
        conn = get_db()
        c = conn.cursor()
        user_id = session['user_id']
        
        # Update last_feed_view
        now = datetime.now().isoformat()
        c.execute("UPDATE users SET last_feed_view = ? WHERE id = ?", (now, user_id))
        
        # Fetch friend_count (safe, as friendships may not exist)
        try:
            c.execute('''
                SELECT u.id FROM users u
                WHERE u.id IN (
                    SELECT target_id FROM friendships WHERE requester_id = ? AND status = 'approved'
                    UNION
                    SELECT requester_id FROM friendships WHERE target_id = ? AND status = 'approved'
                )
            ''', (user_id, user_id))
            friend_ids = [row['id'] for row in c.fetchall()]
        except Exception as f_err:
            logger.warning(f"Friendships query failed: {f_err}")
            friend_ids = []
        
        # Fetch posts with sort (core feed, prioritize this)
        sort = request.args.get('sort', 'latest')
        if sort == 'latest':
            order_by = 'p.created_at DESC'
        elif sort == 'most_views':
            order_by = 'p.views DESC'
        elif sort == 'most_likes':
            order_by = 'p.likes DESC'
        else:
            order_by = 'p.created_at DESC'
            sort = 'latest'

        # FIXED: Use parameterized query to avoid SQL injection in CASE
        c.execute('''
            SELECT p.*, u.handle as post_handle,
                   (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
                   (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            ORDER BY {}
            LIMIT 20
        '''.format(order_by), (user_id, user_id))
        posts = c.fetchall()
        
        # Fetch comments
        comments = {}
        for post in posts:
            try:
                c.execute("SELECT c.*, u.handle as comment_handle FROM comments c JOIN users u ON c.user_id = u.id WHERE post_id = ? ORDER BY c.created_at ASC", (post['id'],))
                comments[post['id']] = c.fetchall()
            except Exception as com_err:
                logger.warning(f"Comments fetch failed for post {post['id']}: {com_err}")
                comments[post['id']] = []
        
        # Increment views
        for post in posts:
            c.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post['id'],))
        
        conn.commit()
        
        # User data
        c.execute("SELECT handle, grade, star_coins, points FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        if user:
            session['handle'] = user['handle'] or session.get('email', 'User')
        
        # Recent test (safe fallback)
        try:
            c.execute("SELECT grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
            recent_test = c.fetchone()
        except:
            recent_test = None
        
        # Lessons completed count
        try:
            c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ?", (user_id,))
            lessons_completed = c.fetchone()['count']
        except:
            lessons_completed = 0
        
        # Games played
        try:
            c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (user_id,))
            games_played = c.fetchone()['count']
        except:
            games_played = 0
        
        # Avg score
        try:
            c.execute("SELECT AVG(score) as avg FROM tests WHERE user_id = ?", (user_id,))
            avg_result = c.fetchone()
            avg_score = round(avg_result['avg'], 1) if avg_result and avg_result['avg'] else 'N/A'
        except:
            avg_score = 'N/A'
        
        # Badges
        try:
            c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (user_id,))
            badges = c.fetchall()
        except:
            badges = []
        
        # Feedbacks
        try:
            c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (user_id,))
            feedbacks = c.fetchall()
        except:
            feedbacks = []
        
        # Lesson feed (isolated try for safety)
        try:
            c.execute("SELECT l.*, lu.assigned_at FROM lessons l JOIN lessons_users lu ON l.id = lu.lesson_id WHERE lu.user_id = ? ORDER BY lu.assigned_at DESC LIMIT 10", (user_id,))
            feed_lessons = c.fetchall()
            c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (user_id,))
            completed_lessons = [row['lesson_id'] for row in c.fetchall()]
        except Exception as lesson_err:
            logger.error(f"Lesson feed failed: {lesson_err}")
            feed_lessons = []
            completed_lessons = []
        
        conn.commit()
        
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
                               feed_lessons=feed_lessons,
                               completed_lessons=completed_lessons,
                               theme=session.get('theme', 'astronaut'),
                               language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Critical home route error: {str(e)}")
        if conn:
            conn.rollback()
        flash('Error loading feed—try again soon!', 'error')
        return render_template('home.html.j2',  # Fallback to empty home render
                               posts=[], comments={}, user=None, recent_test=None,
                               lessons_completed=0, games_played=0, avg_score='N/A',
                               badges=[], feedbacks=[], friend_count=0, sort='latest',
                               feed_lessons=[], completed_lessons=[],
                               theme=session.get('theme', 'astronaut'),
                               language=session.get('language', 'en'))
    finally:
        if conn:
            conn.close()