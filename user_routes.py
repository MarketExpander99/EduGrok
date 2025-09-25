from flask import session, request, jsonify, flash, redirect, url_for, render_template
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from db import get_db

def filter_content(content):  # Duplicate if needed
    pass

def profile():
    logger.debug("Profile route")
    if 'user_id' not in session:
        logger.debug("No user_id in session, redirecting to login")
        flash('Login required', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        if not user:
            logger.error(f"No user found for user_id {session['user_id']}")
            flash('User not found. Please log in again.', 'error')
            session.pop('user_id', None)
            return redirect(url_for('login'))
        
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND completed = 1 AND grade = ?", (session['user_id'], session['grade']))
        lessons_completed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ?", (session['user_id'], session['grade']))
        total_lessons = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM games WHERE user_id = ?", (session['user_id'],))
        games_played = c.fetchone()[0]
        c.execute("SELECT AVG(score) FROM tests WHERE user_id = ?", (session['user_id'],))
        avg_score = round(c.fetchone()[0] or 0, 1)
        c.execute("SELECT points FROM user_points WHERE user_id = ?", (session['user_id'],))
        result = c.fetchone()
        points = result['points'] if result else 0
        c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (session['user_id'],))
        badges = [dict(row) for row in c.fetchall()]
        c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (session['user_id'],))
        feedbacks = [dict(row) for row in c.fetchall()]
        logger.info(f"User {session['user_id']} accessed profile")
        return render_template('profile.html.j2', 
                              user=user,
                              lessons_completed=f"{lessons_completed}/{total_lessons}",
                              games_played=games_played,
                              avg_score=avg_score,
                              grade=session.get('grade', 1),
                              theme=session.get('theme', 'astronaut'),
                              language=session.get('language', 'en'),
                              points=points,
                              star_coins=user['star_coins'] if user['star_coins'] is not None else 0,
                              badges=badges,
                              feedbacks=feedbacks)
    except Exception as e:
        logger.error(f"Profile route failed: {str(e)}")
        flash('Failed to load profile. Try logging in again.', 'error')
        return render_template('error.html.j2', 
                              error=f"Failed to load profile: {str(e)}", 
                              theme=session.get('theme', 'astronaut'), 
                              language=session.get('language', 'en')), 500

def parent_dashboard():
    logger.debug("Parent dashboard route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT 
                COUNT(*) as total_lessons,
                SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) as completed_lessons,
                AVG(t.score) as avg_test_score,
                COALESCE(p.points, 0) as total_points,
                (SELECT COUNT(*) FROM badges WHERE user_id = ?) as badges_count
            FROM lessons l 
            LEFT JOIN tests t ON l.user_id = t.user_id AND l.grade = t.grade
            LEFT JOIN user_points p ON l.user_id = p.user_id
            WHERE l.user_id = ? AND l.grade = ?
        """, (session['user_id'], session['user_id'], session['grade']))
        stats = c.fetchone()
        logger.info(f"User {session['user_id']} accessed parent dashboard")
        return render_template('parent_dashboard.html.j2', stats=stats, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Parent dashboard failed: {str(e)}")
        return render_template('error.html.j2', error="Failed to load dashboard.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

def update_points():
    logger.debug("Update points route")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        points_award = int(data.get('points', 0))
        if points_award <= 0 or points_award > 20:
            return jsonify({'success': False, 'error': 'Invalid points'}), 400
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", 
                  (session['user_id'], session['user_id'], points_award))
        conn.commit()
        logger.info(f"Awarded {points_award} points to user {session['user_id']}")
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Update points failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def update_coins():
    logger.debug("Update coins route")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json()
    coins = int(data.get('coins', 0))
    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT star_coins FROM users WHERE id = ?", (user_id,))
        current_coins = c.fetchone()['star_coins'] or 0
        if current_coins + coins < 0:
            return jsonify({'success': False, 'error': 'Not enough coins'}), 400
        c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (coins, user_id))
        if coins == -10:
            c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, ?, ?)", 
                      (user_id, 'Coin Redeemer', datetime.now().isoformat()))
        conn.commit()
        logger.info(f"Updated {coins} Star Coins for user {user_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coins: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500

def beta():
    logger.debug("Beta route")
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            logger.info(f"Beta invite requested: {email}")
            flash('Thanks! You\'re on the beta list. Check your email soon.', 'success')
        return redirect(url_for('landing'))
    return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def feedback():
    logger.debug("Feedback route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            rating = int(request.form.get('rating', 0))
            comments = filter_content(request.form.get('comments', ''))
            if not 1 <= rating <= 5:
                flash('Rating must be between 1 and 5', 'error')
                return redirect(url_for('feedback'))
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO feedback (user_id, rating, comments, submitted_date) VALUES (?, ?, ?, ?)",
                     (session['user_id'], rating, comments, datetime.now().isoformat()))
            conn.commit()
            flash('Feedback submitted', 'success')
            logger.info(f"User {session['user_id']} submitted feedback: rating={rating}")
            return redirect(url_for('profile'))
        except Exception as e:
            logger.error(f"Feedback submission failed: {str(e)}")
            conn.rollback()
            flash('Server error', 'error')
            return redirect(url_for('feedback'))
    return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))