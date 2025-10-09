# [auth.py]
from flask import jsonify, request, render_template, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db
import logging
import sqlite3

logger = logging.getLogger(__name__)

def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        grade = request.form.get('grade', '1')
        handle = request.form.get('handle', email)
        logger.debug(f"Attempting registration with email: {email}, grade: {grade}, handle: {handle}")
        if not email or not password or not grade.isdigit() or int(grade) not in [1, 2, 3]:
            logger.error(f"Registration failed: Invalid input - email={email}, grade={grade}, password={'set' if password else 'missing'}")
            flash("Invalid email, password, or grade (1-3)", "error")
            return render_template('register.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        if len(password) < 6:
            logger.error(f"Registration failed: Password too short for email={email}")
            flash("Password must be at least 6 characters", "error")
            return render_template('register.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        try:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            logger.debug(f"Generated hash for {email}: {hashed_password}")
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, grade, theme, subscribed, handle, language, star_coins, points, parent_id, role, profile_picture) VALUES (?, ?, ?, 'astronaut', 0, ?, 'en', 0, 0, NULL, 'parent', '')", 
                      (email, hashed_password, int(grade), handle))
            conn.commit()
            logger.info(f"Parent user registered: {email}")
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            logger.error(f"Registration failed: Email {email} already exists - {str(e)}")
            flash("Email already registered", "error")
            return render_template('register.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            flash("Server error during registration", "error")
            return render_template('register.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    return render_template('register.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            logger.error("Login failed: Missing email or password")
            flash("Email and password required", "error")
            return render_template('login.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, password, grade, theme, language, handle, role, profile_picture FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            if user:
                logger.debug(f"Found user {email}, stored hash: {user['password']}")
                if check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['email'] = email  # FIXED: Set email for fallback
                    session['grade'] = user['grade'] or 1
                    session['theme'] = user['theme'] or 'astronaut'
                    session['language'] = user['language'] or 'en'
                    session['handle'] = user['handle'] or email
                    session['role'] = user['role'] or 'parent'
                    session['profile_picture'] = user['profile_picture'] or ''
                    logger.info(f"User logged in: {email}, role: {session['role']}")
                    flash("Login successful!", "success")
                    return redirect(url_for('home'))
                else:
                    logger.error(f"Login failed: Password mismatch for {email}")
                    flash("Invalid email or password", "error")
            else:
                logger.error(f"Login failed: User {email} not found")
                flash("Invalid email or password", "error")
            return render_template('login.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            flash("Server error during login", "error")
            return render_template('login.html.j2', 
                                 theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    return render_template('login.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def logout():
    session.clear()
    logger.info("User logged out")
    flash("Logged out successfully", "success")
    return redirect(url_for('landing'))

def set_theme():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    theme = request.form.get('theme')
    if theme not in ['astronaut', 'farm', 'space']:
        return jsonify({'success': False, 'error': 'Invalid theme'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, session['user_id']))
        conn.commit()
        session['theme'] = theme
        logger.info(f"Theme updated to {theme} for user {session['user_id']}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Set theme failed: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Server error'}), 500
        flash("Failed to update theme", "error")
        return redirect(url_for('lessons'))

def set_language():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    language = request.form.get('language')
    if language not in ['en', 'bilingual']:
        return jsonify({'success': False, 'error': 'Invalid language'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE id = ?", (language, session['user_id']))
        conn.commit()
        session['language'] = language
        logger.info(f"Language updated to {language} for user {session['user_id']}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Set language failed: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Server error'}), 500
        flash("Failed to update language", "error")
        return redirect(url_for('lessons'))