from flask import session, request, flash, redirect, url_for, jsonify, current_app
import logging
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from utils import filter_content, embed_links, allowed_file

logger = logging.getLogger(__name__)

from db import get_db

def create_post():
    logger.debug("Creating post")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    content = filter_content(request.form.get('content', ''))
    subject = request.form.get('subject', 'General')
    if not content:
        flash('Post content is required', 'error')
        return redirect(url_for('home'))
    
    media_url = None
    if 'media' in request.files:
        file = request.files['media']
        if file.filename != '':
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                media_url = f"/static/uploads/{filename}"
    
    # Handle external links
    content = embed_links(content)
    
    try:
        conn = get_db()
        user_id = session.get('user_id')
        handle = session.get('handle', 'User')
        grade = session.get('grade', 1)
        conn.execute('INSERT INTO posts (user_id, handle, content, subject, grade, created_at, media_url, views, reposts) VALUES (?, ?, ?, ?, ?, datetime("now"), ?, 0, 0)',
                     (user_id, handle, content, subject, grade, media_url))
        conn.commit()
        flash('Post created successfully', 'success')
        logger.info(f"User {user_id} created post: {content[:50]}...")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Create post failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('home'))

def like_post(post_id):
    logger.debug(f"Liking post {post_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM post_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Already liked'}), 400
        c.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, session['user_id']))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        conn.commit()
        logger.info(f"User {session['user_id']} liked post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Like post failed: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def repost_post(post_id):
    logger.debug(f"Reposting post {post_id}")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM reposts WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Already reposted'}), 400
        c.execute("INSERT INTO reposts (user_id, post_id, created_at) VALUES (?, ?, datetime('now'))", (session['user_id'], post_id))
        c.execute("UPDATE posts SET reposts = reposts + 1 WHERE id = ?", (post_id,))
        conn.commit()
        logger.info(f"User {session['user_id']} reposted post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Repost failed: {str(e)}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def add_comment(post_id):
    logger.debug(f"Adding comment to post {post_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    content = request.form.get('content', '').strip()
    if not content:
        flash('Comment cannot be empty', 'error')
        return redirect(url_for('home'))
    content = filter_content(content)
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, datetime('now'))",
                  (post_id, session['user_id'], content))
        conn.commit()
        flash('Comment added successfully', 'success')
        logger.info(f"User {session['user_id']} commented on post {post_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Comment failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('home'))