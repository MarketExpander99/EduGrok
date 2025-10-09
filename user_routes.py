# [user_routes.py]
import os
import sqlite3
from flask import jsonify, session, request, flash, redirect, url_for, render_template, current_app
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from db import get_db
from utils import allowed_file

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

        # Fetch user data including role and profile_picture
        c.execute("SELECT id, handle, grade, star_coins, points, theme, language, role, profile_picture FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        if not user:
            logger.error(f"User not found for ID: {session['user_id']}")
            flash("User not found. Please log in again.", "error")
            return redirect(url_for('login'))
        
        # Update session with latest profile_picture
        session['profile_picture'] = user['profile_picture'] or ''

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

        # Fetch linked kids if parent
        kids = []
        if user['role'] == 'parent':
            c.execute("SELECT id, handle, grade, profile_picture FROM users WHERE parent_id = ? AND role = 'kid'", (session['user_id'],))
            kids = [dict(row) for row in c.fetchall()]

        logger.info(f"Profile loaded for user {session['user_id']}: handle={user['handle']}, role={user['role']}, kids={len(kids)}")
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
            kids=kids,
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

def register_child():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is parent
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (session['user_id'],))
    user_row = c.fetchone()
    if not user_row or user_row['role'] != 'parent':
        flash("Only parents can register children.", "error")
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        grade = request.form.get('grade', '1')
        handle = request.form.get('handle', email)
        
        if not email or not password or not grade.isdigit() or int(grade) not in [1, 2, 3]:
            flash("Invalid email, password, or grade (1-3)", "error")
            return render_template('register_child.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        
        if len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return render_template('register_child.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        
        try:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            c.execute("INSERT INTO users (email, password, grade, handle, theme, subscribed, language, star_coins, points, parent_id, role, profile_picture) VALUES (?, ?, ?, ?, 'astronaut', 0, 'en', 0, 0, ?, 'kid', '')", 
                      (email, hashed_password, int(grade), handle, session['user_id']))
            child_id = c.lastrowid
            # Create approved friendship between parent and child
            now = datetime.now().isoformat()
            c.execute("""
                INSERT INTO friendships (requester_id, target_id, status, requested_at, approved_at)
                VALUES (?, ?, 'approved', ?, ?)
            """, (session['user_id'], child_id, now, now))
            conn.commit()
            logger.info(f"Child registered by parent {session['user_id']}: {email}, friendship created")
            flash("Child registered successfully!", "success")
            return redirect(url_for('profile'))
        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
        except Exception as e:
            logger.error(f"Child registration failed: {str(e)}")
            flash("Server error during registration", "error")
        finally:
            conn.close()
    
    return render_template('register_child.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def parent_dashboard():
    logger.debug("Parent dashboard route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()

        # NEW: Check user role - redirect kids to home
        c.execute("SELECT role FROM users WHERE id = ?", (session['user_id'],))
        user_row = c.fetchone()
        if not user_row or user_row['role'] == 'kid':
            flash("Child accounts have access to the feed and games only. Ask your parent for dashboard access!", "info")
            return redirect(url_for('home'))

        # Fetch kids
        c.execute("SELECT id, handle, grade FROM users WHERE parent_id = ? AND role = 'kid'", (session['user_id'],))
        kids = [dict(row) for row in c.fetchall()]
        if not kids:
            logger.warning(f"No kids found for parent {session['user_id']}")
            return render_template('parent_dashboard.html.j2', 
                                 error="No children linked to your account. Please register a child first.",
                                 kids=[],
                                 theme=session.get('theme', 'astronaut'), 
                                 language=session.get('language', 'en'))

        # Get selected kid_id from query param, default to first kid
        selected_kid_id = request.args.get('kid_id', type=int, default=kids[0]['id'])

        # Fetch data for selected kid
        lessons_completed = 0
        games_played = 0
        avg_score = 'N/A'
        badges = []
        tests = []
        feedbacks = []
        pending_lessons = []

        if selected_kid_id:
            # Fetch lessons completed (confirmed)
            c.execute("SELECT COUNT(*) as count FROM completed_lessons WHERE user_id = ? AND parent_confirmed = 1", (selected_kid_id,))
            lessons_completed = c.fetchone()['count'] or 0

            # Fetch games played
            c.execute("SELECT COUNT(*) as count FROM games WHERE user_id = ?", (selected_kid_id,))
            games_played = c.fetchone()['count'] or 0

            # Fetch average test score
            c.execute("SELECT AVG(score) as avg_score FROM tests WHERE user_id = ?", (selected_kid_id,))
            avg_score_result = c.fetchone()['avg_score']
            avg_score = round(avg_score_result, 1) if avg_score_result else 'N/A'

            # Fetch badges
            c.execute("SELECT badge_name, awarded_date FROM badges WHERE user_id = ?", (selected_kid_id,))
            badges = [dict(row) for row in c.fetchall()]

            # Fetch recent tests
            c.execute("SELECT grade, score, date FROM tests WHERE user_id = ? ORDER BY date DESC LIMIT 5", (selected_kid_id,))
            tests = [dict(row) for row in c.fetchall()]

            # Fetch feedbacks
            c.execute("SELECT rating, comments, submitted_date FROM feedback WHERE user_id = ?", (selected_kid_id,))
            feedbacks = [dict(row) for row in c.fetchall()]

            # Fetch pending completed lessons
            c.execute("""
                SELECT cl.id, cl.lesson_id, cl.completed_at, l.title, l.subject, l.grade 
                FROM completed_lessons cl 
                JOIN lessons l ON cl.lesson_id = l.id 
                WHERE cl.user_id = ? AND cl.parent_confirmed = 0
                ORDER BY cl.completed_at DESC
            """, (selected_kid_id,))
            pending_cl = c.fetchall()

            for cl in pending_cl:
                cl_dict = dict(cl)
                # Compute stats from activity_responses
                c.execute("SELECT COUNT(*) as total, SUM(is_correct) as correct FROM activity_responses WHERE lesson_id = ? AND user_id = ?", (cl['lesson_id'], selected_kid_id))
                stats = c.fetchone()
                cl_dict['total_activities'] = stats['total'] or 0
                cl_dict['correct_answers'] = stats['correct'] or 0
                pending_lessons.append(cl_dict)

        # Get selected kid handle
        selected_kid_handle = next((kid['handle'] for kid in kids if kid['id'] == selected_kid_id), kids[0]['handle'])

        logger.info(f"Parent dashboard loaded for parent {session['user_id']}, selected kid {selected_kid_id}: {len(pending_lessons)} pending lessons")
        return render_template(
            'parent_dashboard.html.j2',
            kids=kids,
            selected_kid_id=selected_kid_id,
            kid_handle=selected_kid_handle,
            lessons_completed=lessons_completed,
            games_played=games_played,
            avg_score=avg_score,
            badges=badges,
            tests=tests,
            feedbacks=feedbacks,
            pending_lessons=pending_lessons,
            theme=session.get('theme', 'astronaut'),
            language=session.get('language', 'en')
        )
    except Exception as e:
        logger.error(f"Parent dashboard failed for user {session['user_id']}: {str(e)}")
        return render_template('parent_dashboard.html.j2', 
                             error="Failed to load dashboard.",
                             kids=[],
                             theme=session.get('theme', 'astronaut'), 
                             language=session.get('language', 'en')), 500
    finally:
        if conn:
            conn.close()

def confirm_lesson(lesson_id):
    if request.method != 'POST':
        return jsonify({'success': False, 'error': 'Method not allowed'}), 405
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()

        # Fetch kid_id (assume first kid)
        c.execute("SELECT id FROM users WHERE parent_id = ? AND role = 'kid' LIMIT 1", (session['user_id'],))
        kid_row = c.fetchone()
        if not kid_row:
            return jsonify({'success': False, 'error': 'No child found'}), 404
        kid_id = kid_row['id']

        # Update completed_lessons
        c.execute("UPDATE completed_lessons SET parent_confirmed = 1 WHERE lesson_id = ? AND user_id = ? AND parent_confirmed = 0", (lesson_id, kid_id))
        updated = c.rowcount

        if updated > 0:
            # Delete the lesson post
            c.execute("DELETE FROM posts WHERE type = 'lesson' AND lesson_id = ? AND user_id = ?", (lesson_id, kid_id))
            conn.commit()
            logger.info(f"Parent {session['user_id']} confirmed lesson {lesson_id} for kid {kid_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Lesson not found or already confirmed'}), 404

    except Exception as e:
        logger.error(f"Confirm lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

def restore_lesson(lesson_id):
    if request.method != 'POST':
        return jsonify({'success': False, 'error': 'Method not allowed'}), 405
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()

        # Fetch kid_id (assume first kid)
        c.execute("SELECT id, handle FROM users WHERE parent_id = ? AND role = 'kid' LIMIT 1", (session['user_id'],))
        kid_row = c.fetchone()
        if not kid_row:
            return jsonify({'success': False, 'error': 'No child found'}), 404
        kid_id = kid_row['id']
        kid_handle = kid_row['handle']

        # Reset lessons_users
        c.execute("UPDATE lessons_users SET completed = 0 WHERE lesson_id = ? AND user_id = ?", (lesson_id, kid_id))

        # Delete from completed_lessons
        c.execute("DELETE FROM completed_lessons WHERE lesson_id = ? AND user_id = ?", (lesson_id, kid_id))

        # Re-create lesson post
        c.execute("SELECT title, subject, grade, description FROM lessons WHERE id = ?", (lesson_id,))
        lesson = c.fetchone()
        if lesson:
            now = datetime.now().isoformat()
            content = f"{lesson['title']} - {lesson['description'][:100]}..." if lesson['description'] else lesson['title']
            c.execute("""
                INSERT INTO posts (user_id, content, created_at, likes, reposts, views, subject, grade, handle, type, lesson_id)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?, 'lesson', ?)
            """, (kid_id, content, now, lesson['subject'], lesson['grade'], kid_handle, lesson_id))
            conn.commit()
            logger.info(f"Parent {session['user_id']} restored lesson {lesson_id} for kid {kid_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404

    except Exception as e:
        logger.error(f"Restore lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

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

def update_profile_picture():
    if 'user_id' not in session:
        flash('Please log in to update profile picture', 'error')
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        file = request.files.get('profile_picture')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            profile_url = f'/static/uploads/{filename}'
            conn = None
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE users SET profile_picture = ? WHERE id = ?", (profile_url, session['user_id']))
                conn.commit()
                session['profile_picture'] = profile_url
                logger.info(f"Profile picture updated for user {session['user_id']}: {profile_url}")
                flash('Profile picture updated successfully!', 'success')
            except Exception as e:
                logger.error(f"Update profile picture failed for user {session['user_id']}: {str(e)}")
                flash('Server error updating profile picture', 'error')
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
        else:
            flash('Invalid file. Please upload a valid image (png, jpg, jpeg, gif).', 'error')
    
    return redirect(url_for('profile'))

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