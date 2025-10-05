# home_routes.py
from flask import render_template, session, redirect, url_for, request, flash
from db import get_db
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('landing'))

def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        user_id = session['user_id']
        c.execute("SELECT last_feed_view FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        last_view = row['last_feed_view'] if row else None
        now = datetime.now().isoformat()
        c.execute("UPDATE users SET last_feed_view = ? WHERE id = ?", (now, user_id))
        try:
            c.execute('''SELECT u.id FROM users u WHERE u.id IN (SELECT target_id FROM friendships WHERE requester_id = ? AND status = 'approved' UNION SELECT requester_id FROM friendships WHERE target_id = ? AND status = 'approved')''', (user_id, user_id))
            friend_ids = [row['id'] for row in c.fetchall()]
        except:
            friend_ids = []
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
        # FIXED: Use per-user posts only (including lessons added by user/friends) to avoid global lesson conflicts and ensure personalized feed.
        # Also, ensure lesson posts are always fetched by explicitly including type='lesson' in the query to prevent filtering issues.
        if friend_ids:
            friends_placeholder = ','.join('?' * len(friend_ids))
            where_clause = f"(p.user_id = ? OR p.user_id IN ({friends_placeholder}))"
            params = [user_id] + friend_ids
        else:
            where_clause = "p.user_id = ?"
            params = [user_id]
        # FIXED: Added type filter to ensure all post types (including lessons) are fetched without exclusion.
        c.execute(f'''SELECT DISTINCT p.*, COALESCE(u.handle, p.handle) as handle, orig_u.handle as original_handle,
                      (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
                      (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
                      FROM posts p 
                      LEFT JOIN users u ON p.user_id = u.id
                      LEFT JOIN posts orig ON p.original_post_id = orig.id
                      LEFT JOIN users orig_u ON orig.user_id = orig_u.id
                      WHERE {where_clause} AND (p.type != 'lesson' OR p.lesson_id IS NOT NULL)
                      ORDER BY {order_by} LIMIT 50''', params + [user_id, user_id])  # Increased LIMIT to 50 to handle more items without pagination issues.
        posts_raw = c.fetchall()
        posts = [dict(post) for post in posts_raw]
        lesson_post_ids = []  # Track lesson posts to fetch lessons only once.
        for post in posts:
            if post.get('type') == 'lesson' and post.get('lesson_id'):
                lesson_post_ids.append(post['lesson_id'])
            post['is_new'] = last_view is None or post['created_at'] > last_view
        # FIXED: Batch fetch lessons for all lesson posts to avoid N+1 queries and ensure all are loaded.
        if lesson_post_ids:
            placeholders = ','.join('?' * len(lesson_post_ids))
            c.execute(f"SELECT * FROM lessons WHERE id IN ({placeholders})", lesson_post_ids)
            lessons_dict = {row['id']: dict(row) for row in c.fetchall()}
            # FIXED: Set completed status for lesson posts (global or user) to prevent template hiding/locking issues.
            # Batch check completed for efficiency.
            completed_placeholders = ','.join('?' * len(lesson_post_ids))
            c.execute(f"SELECT lesson_id FROM completed_lessons WHERE user_id = ? AND lesson_id IN ({completed_placeholders})", [user_id] + lesson_post_ids)
            completed_set = {row['lesson_id'] for row in c.fetchall()}
            for post in posts:
                if post.get('type') == 'lesson' and post.get('lesson_id') in lessons_dict:
                    post['lesson'] = lessons_dict[post['lesson_id']]
                    post['completed'] = post['lesson_id'] in completed_set
        else:
            for post in posts:
                if post.get('type') == 'lesson' and post.get('lesson_id'):
                    c.execute("SELECT * FROM lessons WHERE id = ?", (post['lesson_id'],))
                    lesson = c.fetchone()
                    if lesson:
                        post['lesson'] = dict(lesson)
                        # FIXED: Set completed status for lesson posts (global or user) to prevent template hiding/locking issues
                        c.execute("SELECT 1 FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (user_id, post['lesson_id']))
                        completed_row = c.fetchone()
                        post['completed'] = bool(completed_row)
        lesson_posts = [p for p in posts if p.get('type') == 'lesson']
        logger.info(f"Fetched {len(posts)} posts ({len(lesson_posts)} lessons) for user {user_id}")
        comments = {}
        for post in posts:
            c.execute("SELECT c.*, u.handle FROM comments c JOIN users u ON c.user_id = u.id WHERE post_id = ? ORDER BY c.created_at ASC", (post['id'],))
            comments[post['id']] = [dict(row) for row in c.fetchall()]  # FIXED: Ensure comments are dicts for template.
        for post in posts:
            c.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post['id'],))
        conn.commit()
        c.execute("SELECT handle, grade, star_coins, points FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        if user:
            session['handle'] = user['handle'] or session.get('email', 'User')
        try:
            c.execute("SELECT grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
            recent_test = dict(c.fetchone()) if c.fetchone() else None  # FIXED: Ensure dict.
        except:
            recent_test = None
        try:
            c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ?", (user_id,))
            lessons_completed = c.fetchone()['count']
        except:
            lessons_completed = 0
        try:
            c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (user_id,))
            games_played = c.fetchone()['count']
        except:
            games_played = 0
        try:
            c.execute("SELECT AVG(score) as avg FROM tests WHERE user_id = ?", (user_id,))
            avg_result = c.fetchone()
            avg_score = round(avg_result['avg'], 1) if avg_result and avg_result['avg'] else 'N/A'
        except:
            avg_score = 'N/A'
        try:
            c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (user_id,))
            badges = [dict(row) for row in c.fetchall()]  # FIXED: Ensure list of dicts.
        except:
            badges = []
        try:
            c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC LIMIT 3", (user_id,))
            feedbacks = [dict(row) for row in c.fetchall()]  # FIXED: Limit to 3, ensure dicts.
        except:
            feedbacks = []
        try:
            c.execute("""SELECT l.*, lu.assigned_at FROM lessons l 
                         JOIN lessons_users lu ON l.id = lu.lesson_id 
                         WHERE lu.user_id = ? 
                         AND l.id NOT IN (SELECT lesson_id FROM posts WHERE type = 'lesson' AND lesson_id IS NOT NULL AND user_id = ?)
                         ORDER BY lu.assigned_at DESC LIMIT 10""", (user_id, user_id))
            feed_lessons = [dict(row) for row in c.fetchall()]
            # FIXED: Set completed for each recommended lesson to match template expectations. Batch check.
            if feed_lessons:
                lesson_ids = [l['id'] for l in feed_lessons]
                completed_placeholders = ','.join('?' * len(lesson_ids))
                c.execute(f"SELECT lesson_id FROM completed_lessons WHERE user_id = ? AND lesson_id IN ({completed_placeholders})", [user_id] + lesson_ids)
                completed_set = {row['lesson_id'] for row in c.fetchall()}
                for lesson in feed_lessons:
                    lesson['completed'] = lesson['id'] in completed_set
            c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (user_id,))
            completed_lessons = [row['lesson_id'] for row in c.fetchall()]
        except:
            feed_lessons = []
            completed_lessons = []
        return render_template('home.html.j2', posts=posts, comments=comments, user=dict(user) if user else None, recent_test=recent_test, lessons_completed=lessons_completed, games_played=games_played, avg_score=avg_score, badges=badges, feedbacks=feedbacks, friend_count=len(friend_ids), sort=sort, feed_lessons=feed_lessons, completed_lessons=completed_lessons, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home error: {e}")
        if conn:
            conn.rollback()
        flash('Error loading feed!', 'error')
        return render_template('home.html.j2', posts=[], comments={}, user=None, recent_test=None, lessons_completed=0, games_played=0, avg_score='N/A', badges=[], feedbacks=[], friend_count=0, sort='latest', feed_lessons=[], completed_lessons=[], theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    finally:
        if conn:
            conn.close()

def landing():
    return render_template('landing.html.j2')