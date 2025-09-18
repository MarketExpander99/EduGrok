from flask import request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from db import get_db

logger = logging.getLogger(__name__)

def register():
    logger.debug(f"Register route - Session: {session}")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        theme = request.form.get('theme', 'astronaut')
        language = request.form.get('language', 'en')
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password, theme, handle, language) VALUES (?, ?, ?, ?, ?)", (email, hashed_password, theme, email, language))
            conn.commit()
            session['user_id'] = c.lastrowid
            session['email'] = email
            session['theme'] = theme
            session['language'] = language
            logger.info(f"Registered: {email} - User ID: {session['user_id']}")
            return redirect(url_for('assess'))
        except Exception as e:
            if "UNIQUE constraint failed: users.email" in str(e):
                logger.error(f"Email in use: {email}")
                return render_template('register.html.j2', error="Email already in use", theme=theme, language=language)
            logger.error(f"Register failed: {str(e)}")
            conn.rollback()
            return render_template('register.html.j2', error=f"Server error: {str(e)}", theme=theme, language=language)
    return render_template('register.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def login():
    logger.debug(f"Login route - Session: {session}")
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, password, grade, theme, subscribed, language FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['grade'] = user['grade']
                session['theme'] = user['theme']
                session['subscribed'] = bool(user['subscribed'])
                session['email'] = email
                session['language'] = user['language']
                logger.info(f"Logged in: {email} - User ID: {user['id']}")
                return redirect(url_for('home'))
            logger.error(f"Invalid credentials for email: {email}")
            return render_template('login.html.j2', error="Invalid credentials", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            conn.rollback()
            return render_template('login.html.j2', error=f"Server error: {str(e)}", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    return render_template('login.html.j2', theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def logout():
    logger.debug(f"Logout route - Session before clear: {session}")
    session.clear()
    logger.info("Session cleared")
    return redirect(url_for('landing'))

def set_theme():
    logger.debug(f"Set theme route - Session: {session}")
    if 'user_id' not in session:
        logger.error("Unauthorized access to set_theme")
        return redirect(url_for('login'))
    theme = request.form.get('theme')
    if theme not in ['farm', 'space', 'astronaut']:
        logger.error(f"Invalid theme: {theme}")
        flash('Invalid theme', 'error')
        return redirect(request.referrer or url_for('home'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, session['user_id']))
        conn.commit()
        session['theme'] = theme
        logger.info(f"Theme updated to {theme} for user {session['user_id']}")
        return redirect(request.referrer or url_for('home'))
    except Exception as e:
        logger.error(f"Theme update failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(request.referrer or url_for('home'))

def set_language():
    logger.debug(f"Set language route - Session: {session}")
    if 'user_id' not in session:
        logger.error("Unauthorized access to set_language")
        return redirect(url_for('login'))
    language = request.form.get('language')
    if language not in ['en', 'bilingual']:
        logger.error(f"Invalid language: {language}")
        flash('Invalid language', 'error')
        return redirect(request.referrer or url_for('home'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE id = ?", (language, session['user_id']))
        conn.commit()
        session['language'] = language
        logger.info(f"Language updated to {language} for user {session['user_id']}")
        return redirect(request.referrer or url_for('home'))
    except Exception as e:
        logger.error(f"Language update failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(request.referrer or url_for('home'))