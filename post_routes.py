# post_routes.py
import os
from flask import session, request, jsonify, redirect, url_for, flash, current_app
from db import get_db
from werkzeug.utils import secure_filename
from utils import allowed_file
import logging

logger = logging.getLogger(__name__)

def create_post():
    if 'user_id' not in session:
        flash('Please log in to create a post', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Post content cannot be empty', 'error')
            return redirect(url_for('home'))
        if len(content) > 280:
            flash('Post content too long (max 280 characters)', 'error')
            return redirect(url_for('home'))
        subject = request.form.get('subject', 'General')
        media = request.files.get('media')
        media_url = None
        if media and media.filename and allowed_file(media.filename):
            filename = secure_filename(media.filename)
            media_url = f'/static/uploads/{filename}'
            media.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            logger.info(f"Media uploaded: {media_url}")
        conn = None
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("""INSERT INTO posts 
                         (user_id, content, media_url, created_at, subject, grade, handle) 
                         VALUES (?, ?, ?, datetime('now'), ?, ?, ?)""", 
                      (session['user_id'], content, media_url, subject, session['grade'], session['handle']))
            conn.commit()
            flash('Post created successfully!', 'success')
            logger.info(f"Post created by user {session['user_id']}: {content[:50]}...")
        except Exception as e:
            logger.error(f"Create post failed: {str(e)}")
            flash('Server error creating post', 'error')
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    return redirect(url_for('home'))

def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        # Check if post exists
        c.execute("SELECT id FROM posts WHERE id = ?", (post_id,))
        if not c.fetchone():
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        # Check if already liked
        c.execute("SELECT id FROM likes WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
        existing = c.fetchone()
        if existing:
            # Unlike
            c.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
            c.execute("UPDATE posts SET likes = likes - 1 WHERE id = ?", (post_id,))
            action = 'unliked'
        else:
            # Like
            c.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, session['user_id']))
            c.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
            action = 'liked'
        conn.commit()
        logger.info(f"User {session['user_id']} {action} post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Like post failed for post {post_id}: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

def repost_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        # Check if post exists
        c.execute("SELECT id FROM posts WHERE id = ?", (post_id,))
        if not c.fetchone():
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        # Check if already reposted
        c.execute("SELECT id FROM reposts WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
        existing = c.fetchone()
        if existing:
            # Unrepost
            c.execute("DELETE FROM reposts WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
            c.execute("UPDATE posts SET reposts = reposts - 1 WHERE id = ?", (post_id,))
            action = 'unreposted'
        else:
            # Get original post details
            c.execute("SELECT content, media_url, subject, grade, handle as original_handle FROM posts WHERE id = ?", (post_id,))
            orig = c.fetchone()
            if not orig:
                return jsonify({'success': False, 'error': 'Original post not found'}), 404
            # Insert new repost as a post
            c.execute("""INSERT INTO posts 
                         (user_id, content, media_url, created_at, subject, grade, original_post_id, handle, original_handle) 
                         VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)""", 
                      (session['user_id'], orig['content'], orig['media_url'], orig['subject'], orig['grade'], 
                       post_id, session['handle'], orig['original_handle']))
            # Add to reposts table
            c.execute("INSERT INTO reposts (post_id, user_id) VALUES (?, ?)", (post_id, session['user_id']))
            c.execute("UPDATE posts SET reposts = reposts + 1 WHERE id = ?", (post_id,))
            # Increment views on original
            c.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
            action = 'reposted'
        conn.commit()
        logger.info(f"User {session['user_id']} {action} post {post_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Repost post failed for post {post_id}: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

def add_comment(post_id):
    if 'user_id' not in session:
        flash('Please log in to comment', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Comment cannot be empty', 'error')
            return redirect(url_for('home'))
        conn = None
        try:
            conn = get_db()
            c = conn.cursor()
            # Check if post exists
            c.execute("SELECT id FROM posts WHERE id = ?", (post_id,))
            if not c.fetchone():
                flash('Post not found', 'error')
                return redirect(url_for('home'))
            c.execute("INSERT INTO comments (post_id, user_id, content, created_at, handle) VALUES (?, ?, ?, datetime('now'), ?)", 
                      (post_id, session['user_id'], content, session['handle']))
            conn.commit()
            flash('Comment added successfully!', 'success')
            logger.info(f"Comment added by user {session['user_id']} to post {post_id}: {content[:50]}...")
        except Exception as e:
            logger.error(f"Add comment failed for post {post_id}: {str(e)}")
            if conn:
                conn.rollback()
            flash('Server error adding comment', 'error')
        finally:
            if conn:
                conn.close()
    return redirect(url_for('home'))