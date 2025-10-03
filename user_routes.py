from flask import jsonify, session, request, flash, redirect, url_for, render_template
import logging
from datetime import datetime
from db import get_db

logger = logging.getLogger(__name__)

def profile():
    logger.debug("Profile route")
    if 'user_id' not in session:
        logger.error("Unauthorized access to /profile")
        flash("Please log in to view your profile", "error")
        return redirect(url_for('login'))
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()

        # Fetch user data
        c.execute("SELECT id, handle, grade, star_coins, points, theme, language FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        if not user:
            logger.error(f"User not found for ID: {session['user_id']}")
            flash("User not found. Please log in again.", "error")
            return redirect(url_for('login'))

        # Fetch badges
        c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ?", (session['user_id'],))
        badges = [dict(row) for row in c.fetchall()]

        # Fetch feedback
        c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ?", (session['user_id'],))
        feedbacks = [dict(row) for row in c.fetchall()]

        # Fetch lessons completed
        c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ?", (session['user_id'],))
        lessons_completed = c.fetchone()['count'] or 0

        # Fetch games played
        c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (session['user_id'],))
        games_played = c.fetchone()['count'] or 0

        # Fetch average test score
        c.execute("SELECT AVG(score) as avg_score FROM tests WHERE user_id = ?", (session['user_id'],))
        avg_score_result = c.fetchone()['avg_score']
        avg_score = round(avg_score_result, 1) if avg_score_result else 0

        logger.info(f"Profile loaded for user {session['user_id']}: handle={user['handle']}, grade={user['grade']}")
        return render_template(
            'profile.html.j2',
            user=user,
            grade=user['grade'],
            star_coins=user['star_coins'],
            points=user['points'],
            badges=badges,
            feedbacks=feedbacks,
            lessons_completed=lessons_completed,
            games_played=games_played,
            avg_score=avg_score,
            theme=session.get('theme', 'astronaut'),
            language=session.get('language', 'en')
        )
    except Exception as e:
        logger.error(f"Profile load failed for user {session['user_id']}: {str(e)}")
        flash("Failed to load profile due to a server error.", "error")
        return render_template(
            'error.html.j2',
            error=f"Failed to load profile: {str(e)}",
            theme=session.get('theme', 'astronaut'),
            language=session.get('language', 'en')
        ), 500
    finally:
        if conn:
            conn.close()

def parent_dashboard():
    logger.debug("Parent dashboard route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Placeholder for parent dashboard logic
    return render_template('parent_dashboard.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def update_points():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    points = request.form.get('points', type=int)
    if not points or points < 0:
        return jsonify({'success': False, 'error': 'Invalid points value'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE id = ?", (points, session['user_id']))
        c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, ?, ?)",
                  (session['user_id'], points, datetime.now().isoformat()))
        conn.commit()
        logger.info(f"Updated points for user {session['user_id']}: +{points}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update points failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

def update_coins():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    coins = request.form.get('coins', type=int)
    if not coins or coins < 0:
        return jsonify({'success': False, 'error': 'Invalid coins value'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET star_coins = star_coins + ? WHERE id = ?", (coins, session['user_id']))
        conn.commit()
        logger.info(f"Updated coins for user {session['user_id']}: +{coins}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update coins failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

def beta():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET subscribed = 1 WHERE id = ?", (session['user_id'],))
            conn.commit()
            logger.info(f"User {session['user_id']} subscribed to beta")
            flash("Subscribed to beta successfully!", "success")
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Beta subscription failed: {str(e)}")
            flash("Failed to subscribe to beta", "error")
            return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        finally:
            if conn:
                conn.close()
    return render_template('beta.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        comments = request.form.get('comments')
        if not rating or rating < 1 or rating > 5:
            flash("Invalid rating. Please select a rating between 1 and 5.", "error")
            return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO feedback (user_id, rating, comments, submitted_date) VALUES (?, ?, ?, ?)",
                      (session['user_id'], rating, comments, datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Feedback submitted by user {session['user_id']}: rating={rating}")
            flash("Feedback submitted successfully!", "success")
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Feedback submission failed: {str(e)}")
            flash("Failed to submit feedback", "error")
            return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        finally:
            if conn:
                conn.close()
    return render_template('feedback.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))