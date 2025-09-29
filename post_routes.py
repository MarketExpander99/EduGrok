from flask import request, session, jsonify, flash, redirect, url_for, current_app  # FIXED: Added current_app
import os
import logging
from werkzeug.utils import secure_filename
from db import get_db
from utils import allowed_file

logger = logging.getLogger(__name__)

def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        subject = request.form.get('subject', 'General')
        if len(content) > 280:
            flash('Post too long (max 280 chars)', 'error')
            return redirect(url_for('home'))
        media_url = None
        if 'media' in request.files:
            file = request.files['media']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                media_url = f"/static/uploads/{filename}"
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO posts (user_id, content, subject, media_url) VALUES (?, ?, ?, ?)",
                      (session['user_id'], content, subject, media_url))
            conn.commit()
            flash('Post created successfully!', 'success')
            logger.info(f"User {session['user_id']} created post {c.lastrowid}")
        except Exception as e:
            logger.error(f"Create post failed: {e}")
            conn.rollback()
            flash('Error creating post', 'error')
        return redirect(url_for('home'))
    return redirect(url_for('home'))

def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM post_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            # Unlike
            c.execute("DELETE FROM post_likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
            c.execute("UPDATE posts SET likes = likes - 1 WHERE id = ?", (post_id,))
            action = 'unliked'
        else:
            # Like
            c.execute("INSERT INTO post_likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
            c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
            action = 'liked'
        conn.commit()
        likes = c.execute("SELECT likes FROM posts WHERE id = ?", (post_id,)).fetchone()[0] or 0
        logger.info(f"User {session['user_id']} {action} post {post_id}")
        return jsonify({'success': True, 'likes': likes, 'action': action})
    except Exception as e:
        logger.error(f"Like post failed: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def repost_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM reposts WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        if c.fetchone():
            # Unrepost
            c.execute("DELETE FROM reposts WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
            c.execute("UPDATE posts SET reposts = reposts - 1 WHERE id = ?", (post_id,))
            action = 'unreposted'
        else:
            # Repost: Create new post referencing original
            c.execute("SELECT content, subject, media_url FROM posts WHERE id = ?", (post_id,))
            orig = c.fetchone()
            if orig:
                new_content = f"🔄 Reposted: {orig['content'][:100]}..."  # Truncate if long
                c.execute("INSERT INTO posts (user_id, content, subject, media_url, original_post_id) VALUES (?, ?, ?, ?, ?)",
                          (session['user_id'], new_content, orig['subject'], orig['media_url'], post_id))
                new_post_id = c.lastrowid
                c.execute("INSERT INTO reposts (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
                c.execute("UPDATE posts SET reposts = reposts + 1 WHERE id = ?", (post_id,))
                action = 'reposted'
                logger.info(f"User {session['user_id']} reposted post {post_id} as {new_post_id}")
            else:
                return jsonify({'success': False, 'error': 'Original post not found'}), 404
        conn.commit()
        reposts_count = c.execute("SELECT reposts FROM posts WHERE id = ?", (post_id,)).fetchone()[0] or 0
        return jsonify({'success': True, 'reposts': reposts_count, 'action': action})
    except Exception as e:
        logger.error(f"Repost failed: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def add_comment(post_id):
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('home'))
    content = request.form.get('content', '').strip()
    if not content or len(content) > 280:
        flash('Comment too short or too long', 'error')
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO comments (user_id, post_id, content) VALUES (?, ?, ?)",
                  (session['user_id'], post_id, content))
        conn.commit()
        flash('Comment added!', 'success')
        logger.info(f"User {session['user_id']} commented on post {post_id}")
    except Exception as e:
        logger.error(f"Add comment failed: {e}")
        conn.rollback()
        flash('Error adding comment', 'error')
    return redirect(url_for('home'))