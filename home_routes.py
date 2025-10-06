# [home_routes.py updated: Added subtle kid-friendly note by fetching user role and passing 'is_kid' flag to template for conditional display (e.g., "Explore the feed and play games!"). Preserved all existing feed logic, cleanup, and features.]

from flask import render_template, session, redirect, url_for, request, flash
from db import get_db
import logging
import traceback
import json
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
        logger.info(f"Home for user_id: {user_id}")
        # Fetch user role for kid-mode note
        c.execute("SELECT role FROM users WHERE id=?", (user_id,))
        user_row = c.fetchone()
        is_kid = user_row and user_row['role'] == 'kid' if user_row else False
        # Cleanup invalid lesson posts before fetching
        try:
            c.execute("""
                DELETE FROM posts 
                WHERE type = 'lesson' 
                AND lesson_id IS NOT NULL 
                AND lesson_id NOT IN (SELECT id FROM lessons)
            """)
            deleted = c.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} invalid lesson posts")
                conn.commit()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
        c.execute("SELECT last_feed_view FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        last_view = row['last_feed_view'] if row else None
        now = datetime.now().isoformat()
        c.execute("UPDATE users SET last_feed_view = ? WHERE id = ?", (now, user_id))
        try:
            c.execute('''SELECT u.id FROM users u WHERE u.id IN (SELECT target_id FROM friendships WHERE requester_id = ? AND status = 'approved' UNION SELECT requester_id FROM friendships WHERE target_id = ? AND status = 'approved')''', (user_id, user_id))
            friend_ids = [row['id'] for row in c.fetchall()]
            logger.info(f"Friend IDs: {friend_ids}")
        except Exception as e:
            logger.warning(f"Error fetching friends: {e}")
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

        # FIXED: Separate queries for global posts (type='post') and user-specific lessons (type='lesson')
        # Global posts: from all users
        global_query = f'''SELECT DISTINCT p.*, COALESCE(u.handle, p.handle) as handle, orig_u.handle as original_handle,
                          (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
                          (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
                          FROM posts p 
                          LEFT JOIN users u ON p.user_id = u.id
                          LEFT JOIN posts orig ON p.original_post_id = orig.id
                          LEFT JOIN users orig_u ON orig.user_id = orig_u.id
                          WHERE p.type = 'post'
                          ORDER BY {order_by} LIMIT 20'''
        c.execute(global_query, [user_id, user_id])
        global_posts_raw = c.fetchall()
        global_posts = [dict(post) for post in global_posts_raw]

        # User lessons: only from current user, exclude confirmed (parent_confirmed=1)
        lesson_query = f'''SELECT DISTINCT p.*, COALESCE(u.handle, p.handle) as handle, orig_u.handle as original_handle,
                          (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id AND l.user_id = ?) as liked_by_user,
                          (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id AND r.user_id = ?) as reposted_by_user
                          FROM posts p 
                          LEFT JOIN users u ON p.user_id = u.id
                          LEFT JOIN posts orig ON p.original_post_id = orig.id
                          LEFT JOIN users orig_u ON orig.user_id = orig_u.id
                          LEFT JOIN completed_lessons cl ON cl.lesson_id = p.lesson_id AND cl.user_id = p.user_id
                          WHERE p.type = 'lesson' AND p.user_id = ? AND (cl.parent_confirmed IS NULL OR cl.parent_confirmed = 0)
                          ORDER BY {order_by}'''
        c.execute(lesson_query, [user_id, user_id, user_id])
        lesson_posts_raw = c.fetchall()
        lesson_posts = [dict(post) for post in lesson_posts_raw]

        # Combine and sort all posts
        posts = global_posts + lesson_posts
        posts.sort(key=lambda x: x['created_at'] or '', reverse=True)
        posts = posts[:20]  # Limit total

        logger.info(f"Raw posts fetched: {len(global_posts)} global, {len(lesson_posts)} lessons; Total: {len(posts)}")

        for post in posts:
            try:
                if post.get('type') == 'lesson' and post.get('lesson_id'):
                    c.execute("SELECT * FROM lessons WHERE id = ?", (post['lesson_id'],))
                    lesson = c.fetchone()
                    if lesson:
                        lesson_dict = dict(lesson)
                        # Parse JSON fields to lists
                        if lesson_dict.get('mc_options'):
                            try:
                                lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options']) if lesson_dict['mc_options'] else []
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"Invalid JSON in mc_options for lesson {post['lesson_id']}: {e}")
                                lesson_dict['mc_options'] = []
                        if lesson_dict.get('sentence_options'):
                            try:
                                lesson_dict['sentence_options'] = json.loads(lesson_dict['sentence_options']) if lesson_dict['sentence_options'] else []
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"Invalid JSON in sentence_options for lesson {post['lesson_id']}: {e}")
                                lesson_dict['sentence_options'] = []
                        post['lesson'] = lesson_dict
                        # Set completed status for lesson posts
                        c.execute("SELECT 1 FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (user_id, post['lesson_id']))
                        completed_row = c.fetchone()
                        post['completed'] = bool(completed_row)
                    else:
                        logger.warning(f"Lesson not found for post {post.get('id')}, lesson_id {post.get('lesson_id')}")
            except Exception as e:
                logger.error(f"Error processing lesson for post {post.get('id', 'unknown')}: {e}\n{traceback.format_exc()}")
            post['is_new'] = last_view is None or post['created_at'] > last_view

        # Filter out invalid lesson posts
        original_count = len(posts)
        posts = [p for p in posts if not (p.get('type') == 'lesson' and not p.get('lesson'))]
        removed_count = original_count - len(posts)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} invalid lesson posts from feed for user {user_id}")
        lesson_posts = [p for p in posts if p.get('type') == 'lesson']
        logger.info(f"Total posts after filter: {len(posts)} ({len(lesson_posts)} lessons) for user {user_id}")

        comments = {}
        for post in posts:
            try:
                c.execute("SELECT c.*, u.handle FROM comments c LEFT JOIN users u ON c.user_id = u.id WHERE post_id = ? ORDER BY c.created_at ASC", (post['id'],))
                comments[post['id']] = [dict(row) for row in c.fetchall()]
            except Exception as e:
                logger.error(f"Error fetching comments for post {post['id']}: {e}\n{traceback.format_exc()}")
                comments[post['id']] = []

        for post in posts:
            try:
                c.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post['id'],))
            except Exception as e:
                logger.error(f"Error updating views for post {post['id']}: {e}\n{traceback.format_exc()}")

        conn.commit()

        # User fetch
        try:
            c.execute("SELECT handle, grade, star_coins, points FROM users WHERE id = ?", (user_id,))
            user = c.fetchone()
        except Exception as e:
            logger.error(f"Error fetching user for id {user_id}: {e}\n{traceback.format_exc()}")
            user = None
        if user:
            session['handle'] = user['handle'] or session.get('email', 'User')
        else:
            session['handle'] = session.get('email', 'User')

        # Recent test
        try:
            c.execute("SELECT grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
            recent_test = c.fetchone()
        except Exception as e:
            logger.warning(f"Error fetching recent test: {e}")
            recent_test = None

        # Lessons completed
        try:
            c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ?", (user_id,))
            lessons_completed = c.fetchone()['count']
        except Exception as e:
            logger.warning(f"Error fetching lessons completed: {e}")
            lessons_completed = 0

        # Games played
        try:
            c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (user_id,))
            games_played = c.fetchone()['count']
        except Exception as e:
            logger.warning(f"Error fetching games played: {e}")
            games_played = 0

        # Avg score
        try:
            c.execute("SELECT AVG(score) as avg FROM tests WHERE user_id = ?", (user_id,))
            avg_result = c.fetchone()
            avg_score = round(avg_result['avg'], 1) if avg_result and avg_result['avg'] else 'N/A'
        except Exception as e:
            logger.warning(f"Error fetching avg score: {e}")
            avg_score = 'N/A'

        # Badges
        try:
            c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (user_id,))
            badges = c.fetchall()
        except Exception as e:
            logger.warning(f"Error fetching badges: {e}")
            badges = []

        # Feedbacks
        try:
            c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (user_id,))
            feedbacks = c.fetchall()
        except Exception as e:
            logger.warning(f"Error fetching feedbacks: {e}")
            feedbacks = []

        # Feed lessons (recommended)
        try:
            logger.info("Fetching feed_lessons")
            c.execute("""SELECT l.*, lu.assigned_at FROM lessons l 
                         JOIN lessons_users lu ON l.id = lu.lesson_id 
                         WHERE lu.user_id = ? 
                         AND l.id NOT IN (SELECT lesson_id FROM posts WHERE type = 'lesson' AND lesson_id IS NOT NULL AND user_id = ?)
                         ORDER BY lu.assigned_at DESC LIMIT 10""", (user_id, user_id))
            feed_rows = c.fetchall()
            feed_lessons = []
            for l in feed_rows:
                lesson_dict = dict(l)
                # Parse JSON fields to lists for recommended lessons
                if lesson_dict.get('mc_options'):
                    try:
                        lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options']) if lesson_dict['mc_options'] else []
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid JSON in mc_options for recommended lesson {lesson_dict['id']}: {e}")
                        lesson_dict['mc_options'] = []
                if lesson_dict.get('sentence_options'):
                    try:
                        lesson_dict['sentence_options'] = json.loads(lesson_dict['sentence_options']) if lesson_dict['sentence_options'] else []
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid JSON in sentence_options for recommended lesson {lesson_dict['id']}: {e}")
                        lesson_dict['sentence_options'] = []
                feed_lessons.append(lesson_dict)
            # Set completed for each recommended lesson
            for lesson in feed_lessons:
                c.execute("SELECT 1 FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (user_id, lesson['id']))
                completed_row = c.fetchone()
                lesson['completed'] = bool(completed_row)
            c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (user_id,))
            completed_lessons = [row['lesson_id'] for row in c.fetchall()]
            logger.info(f"Feed lessons fetched: {len(feed_lessons)}")
        except Exception as e:
            logger.error(f"Error fetching feed_lessons: {e}\n{traceback.format_exc()}")
            feed_lessons = []
            completed_lessons = []

        return render_template('home.html.j2', posts=posts, comments=comments, user=user, recent_test=recent_test, lessons_completed=lessons_completed, games_played=games_played, avg_score=avg_score, badges=badges, feedbacks=feedbacks, friend_count=len(friend_ids), sort=sort, feed_lessons=feed_lessons, completed_lessons=completed_lessons, is_kid=is_kid, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Home error for user {user_id}: {str(e)}\n{traceback.format_exc()}")
        if conn:
            conn.rollback()
        flash('Error loading feed! Check server logs for details.', 'error')
        return render_template('home.html.j2', posts=[], comments={}, user=None, recent_test=None, lessons_completed=0, games_played=0, avg_score='N/A', badges=[], feedbacks=[], friend_count=0, sort='latest', feed_lessons=[], completed_lessons=[], is_kid=False, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    finally:
        if conn:
            conn.close()

def landing():
    return render_template('landing.html.j2')