from flask import session, request, jsonify, flash, redirect, url_for, render_template
import logging
from db import get_db

logger = logging.getLogger(__name__)

def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))
        # FIXED: Sum points from multiple earnings
        c.execute("SELECT SUM(points) FROM user_points WHERE user_id = ?", (session['user_id'],))
        points = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM lessons_users WHERE user_id = ? AND completed = 1", (session['user_id'],))
        lessons_completed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM games WHERE user_id = ?", (session['user_id'],))
        games_played = c.fetchone()[0]
        c.execute("SELECT AVG(score) FROM tests WHERE user_id = ?", (session['user_id'],))
        avg_score = round(c.fetchone()[0] or 0, 1)
        c.execute("SELECT * FROM badges WHERE user_id = ? ORDER BY awarded_date DESC", (session['user_id'],))
        badges = c.fetchall()
        c.execute("SELECT * FROM feedback WHERE user_id = ? ORDER BY submitted_date DESC", (session['user_id'],))
        feedbacks = c.fetchall()
        return render_template('profile.html.j2', 
                               user=dict(user), points=points, lessons_completed=lessons_completed,
                               games_played=games_played, avg_score=avg_score, 
                               badges=[dict(b) for b in badges], feedbacks=[dict(f) for f in feedbacks],
                               grade=session['grade'], star_coins=user['star_coins'],
                               theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Profile failed: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('home'))

def parent_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # FIXED: Simple redirect to profile for now (expand for multi-kid if needed; check sub)
    c = get_db().cursor()
    c.execute("SELECT subscribed FROM users WHERE id = ?", (session['user_id'],))
    subscribed = c.fetchone()[0] or 0
    if not subscribed:
        flash('Premium subscription required for dashboard', 'error')
        return redirect(url_for('profile'))
    # Stub: Reuse profile or render dedicated (assuming parent_dashboard.html.j2 exists minimally)
    return redirect(url_for('profile'))  # Or render_template('parent_dashboard.html.j2', ...)

def update_points():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    points = data.get('points', 0)
    if points <= 0:
        return jsonify({'success': False, 'error': 'Invalid points'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, ?, datetime('now'))", 
                  (session['user_id'], points))
        conn.commit()
        logger.info(f"Awarded {points} points to user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update points failed: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def update_coins():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    coins = data.get('coins', 0)
    if coins <= 0:
        return jsonify({'success': False, 'error': 'Invalid coins'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET star_coins = star_coins + ? WHERE id = ?", (coins, session['user_id']))
        conn.commit()
        logger.info(f"Awarded {coins} coins to user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update coins failed: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def beta():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Beta features page (expand as needed)
    return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        rating = request.form.get('rating')
        comments = request.form.get('comments', '')
        if not rating or int(rating) < 1 or int(rating) > 5:
            flash('Rating must be 1-5', 'error')
            return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO feedback (user_id, rating, comments, submitted_date) VALUES (?, ?, ?, datetime('now'))", 
                      (session['user_id'], int(rating), comments))
            conn.commit()
            flash('Feedback submitted! Thanks!', 'success')
            logger.info(f"User {session['user_id']} submitted feedback: {rating}/5")
            return redirect(url_for('profile'))
        except Exception as e:
            logger.error(f"Feedback submit failed: {e}")
            conn.rollback()
            flash('Error submitting feedback', 'error')
        return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))