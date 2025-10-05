# lesson_routes.py (new/fixed: Implemented add_to_feed with per-user check, grade validation, error handling. Added stubs for other functions with basic implementations to make complete. FIXED: Added create_lesson route to handle new lesson creation from form, then auto-add to feed. Ensured new lessons are inserted with user_id, grade match, and immediately added as post. Added logging for debugging add failures. Ensured all dicts for template.)
import logging
import sqlite3
import json
from flask import session, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime
from db import get_db

logger = logging.getLogger(__name__)

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    grade = session.get('grade', 1)
    c.execute("SELECT * FROM lessons WHERE grade = ? ORDER BY created_at DESC", (grade,))
    lessons_list = [dict(row) for row in c.fetchall()]
    # Get completed lessons
    c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (session['user_id'],))
    completed_ids = {row['lesson_id'] for row in c.fetchall()}
    for lesson in lessons_list:
        lesson['completed'] = lesson['id'] in completed_ids
    # Get lessons in feed
    c.execute("SELECT lesson_id FROM posts WHERE user_id = ? AND type = 'lesson'", (session['user_id'],))
    in_feed_ids = {row['lesson_id'] for row in c.fetchall()}
    for lesson in lessons_list:
        lesson['in_feed'] = lesson['id'] in in_feed_ids
    conn.close()
    return render_template('lessons.html.j2', lessons=lessons_list, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def create_lesson():
    # FIXED: New route to handle POST from lessons.html.j2 form for creating a new lesson, then auto-add to feed.
    if 'user_id' not in session or request.method != 'POST':
        return redirect(url_for('lessons'))
    data = request.form  # Assuming form data; adapt if JSON.
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    subject = data.get('subject', 'General')
    grade = int(data.get('grade', session.get('grade', 1)))
    # Optional activities (assuming form fields; store as JSON if needed).
    trace_word = data.get('trace_word', '')
    spell_word = data.get('spell_word', '')
    mc_question = data.get('mc_question', '')
    mc_options = data.get('mc_options', '')  # e.g., "A,B,C,D"
    mc_answer = data.get('mc_answer', '')
    sentence_question = data.get('sentence_question', '')
    sentence_options = data.get('sentence_options', '')
    sentence_answer = data.get('sentence_answer', '')
    math_question = data.get('math_question', '')
    math_answer = data.get('math_answer', '')
    if not title:
        flash('Title is required!', 'error')
        return redirect(url_for('lessons'))
    if grade != session.get('grade', 1):
        flash('Grade mismatch!', 'error')
        return redirect(url_for('lessons'))
    conn = get_db()
    c = conn.cursor()
    try:
        now = datetime.now().isoformat()
        # FIXED: Insert new lesson with user_id for ownership.
        c.execute("""INSERT INTO lessons 
                     (user_id, title, description, subject, grade, trace_word, spell_word, 
                      mc_question, mc_options, mc_answer, sentence_question, sentence_options, sentence_answer, 
                      math_question, math_answer, created_at) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (session['user_id'], title, description, subject, grade, trace_word, spell_word,
                   mc_question, json.dumps(mc_options.split(',')) if mc_options else None, mc_answer,
                   sentence_question, json.dumps(sentence_options.split(',')) if sentence_options else None, sentence_answer,
                   math_question, math_answer, now))
        lesson_id = c.lastrowid
        conn.commit()
        logger.info(f"Created new lesson {lesson_id} for user {session['user_id']}")
        # FIXED: Auto-add to feed immediately after creation to ensure it appears in home.
        add_to_feed_result = add_to_feed_internal(lesson_id)  # Internal call to avoid jsonify.
        if add_to_feed_result['success']:
            flash(f'Lesson "{title}" created and added to feed!', 'success')
        else:
            logger.warning(f"Failed to add new lesson {lesson_id} to feed: {add_to_feed_result.get('error')}")
            flash(f'Lesson "{title}" created, but failed to add to feed: {add_to_feed_result.get("error")}', 'warning')
    except Exception as e:
        logger.error(f"Create lesson error for user {session['user_id']}: {e}")
        conn.rollback()
        flash('Error creating lesson!', 'error')
    finally:
        conn.close()
    return redirect(url_for('lessons'))

def add_to_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    if not lesson_id:
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    result = add_to_feed_internal(lesson_id)
    return jsonify(result)

def add_to_feed_internal(lesson_id):
    # FIXED: Internal helper for add_to_feed to allow calling from create_lesson without HTTP.
    conn = get_db()
    c = conn.cursor()
    try:
        # Check if already added by this user
        c.execute("SELECT id FROM posts WHERE user_id = ? AND lesson_id = ? AND type = 'lesson'", (session['user_id'], lesson_id))
        if c.fetchone():
            return {'success': False, 'message': 'Already in feed'}
        # Get lesson
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson_row = c.fetchone()
        if not lesson_row:
            return {'success': False, 'error': 'Lesson not found'}, 404
        lesson = dict(lesson_row)
        # Validate grade
        if lesson['grade'] != session.get('grade', 1):
            return {'success': False, 'error': 'Grade mismatch'}, 400
        # Insert post
        now = datetime.now().isoformat()
        c.execute("""INSERT INTO posts 
                     (user_id, content, subject, grade, handle, type, lesson_id, created_at, views, likes, reposts) 
                     VALUES (?, ?, ?, ?, ?, 'lesson', ?, ?, 0, 0, 0)""", 
                  (session['user_id'], lesson['title'], lesson['subject'], lesson['grade'], 
                   session.get('handle', session.get('email', 'User')), lesson_id, now))
        post_id = c.lastrowid
        conn.commit()
        logger.info(f"Lesson {lesson_id} (post {post_id}) added to feed for user {session['user_id']}")
        return {'success': True, 'message': 'Added to feed!'}
    except sqlite3.IntegrityError as e:
        logger.warning(f"Add to feed integrity error for user {session['user_id']}, lesson {lesson_id}: {e}")
        conn.rollback()
        return {'success': False, 'error': 'Already exists'}, 409
    except Exception as e:
        logger.error(f"Add to feed error for user {session['user_id']}, lesson {lesson_id}: {e}")
        conn.rollback()
        return {'success': False, 'error': 'Server error'}, 500
    finally:
        conn.close()

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data or 'lesson_id' not in data or 'activity_type' not in data or 'response' not in data:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    lesson_id = data['lesson_id']
    activity_type = data['activity_type']
    response = data['response']
    conn = get_db()
    c = conn.cursor()
    try:
        if activity_type == 'mc':
            c.execute("SELECT mc_answer FROM lessons WHERE id = ?", (lesson_id,))
            correct = c.fetchone()
            correct = correct['mc_answer'] if correct else None
        elif activity_type == 'sentence':
            c.execute("SELECT sentence_answer FROM lessons WHERE id = ?", (lesson_id,))
            correct = c.fetchone()
            correct = correct['sentence_answer'] if correct else None
        elif activity_type == 'math':
            c.execute("SELECT math_answer FROM lessons WHERE id = ?", (lesson_id,))
            correct = c.fetchone()
            correct = correct['math_answer'] if correct else None
        else:
            return jsonify({'success': False, 'error': 'Invalid activity type'}), 400
        if not correct:
            return jsonify({'success': False, 'error': 'Lesson activity not found'}), 404
        is_correct = 1 if str(response).strip() == str(correct).strip() else 0
        points = 10 if is_correct else 0
        now = datetime.now().isoformat()
        c.execute("""INSERT INTO lesson_responses 
                     (lesson_id, user_id, activity_type, response, is_correct, points, responded_at) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                  (lesson_id, session['user_id'], activity_type, response, is_correct, points, now))
        conn.commit()
        return jsonify({'success': True, 'correct': bool(is_correct), 'points': points})
    except Exception as e:
        logger.error(f"Check lesson error: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        conn.close()

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        now = datetime.now().isoformat()
        c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)", 
                  (session['user_id'], lesson_id, now))
        c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        # FIXED: Also update the post's lesson completed status if it's in feed.
        c.execute("UPDATE posts SET completed = 1 WHERE type = 'lesson' AND lesson_id = ? AND user_id = ?", 
                  (lesson_id, session['user_id']))
        conn.commit()
        flash('Lesson completed successfully!', 'success')
    except Exception as e:
        logger.error(f"Complete lesson error: {e}")
        conn.rollback()
        flash('Error completing lesson', 'error')
    finally:
        conn.close()
    return redirect(url_for('home'))  # FIXED: Redirect to home to refresh feed.

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        c.execute("UPDATE lessons_users SET completed = 0 WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        c.execute("DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        # FIXED: Reset post's completed if in feed.
        c.execute("UPDATE posts SET completed = 0 WHERE type = 'lesson' AND lesson_id = ? AND user_id = ?", 
                  (lesson_id, session['user_id']))
        conn.commit()
        flash('Lesson reset successfully!', 'success')
    except Exception as e:
        logger.error(f"Reset lesson error: {e}")
        conn.rollback()
        flash('Error resetting lesson', 'error')
    finally:
        conn.close()
    return redirect(url_for('home'))  # FIXED: Redirect to home.

def generate_lesson():
    # Stub: In a real app, this could generate a new lesson using AI or logic
    flash('Lesson generated! (Stub implementation)', 'success')
    return redirect(url_for('lessons'))

def schedule_lessons():
    # Stub: POST to assign lessons to user
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_ids = data.get('lesson_ids', [])
    if not lesson_ids:
        return jsonify({'success': False, 'error': 'No lessons specified'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        now = datetime.now().isoformat()
        for lid in lesson_ids:
            c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)", 
                      (session['user_id'], lid, now))
        conn.commit()
        return jsonify({'success': True, 'message': f'Added {len(lesson_ids)} lessons to schedule'})
    except Exception as e:
        logger.error(f"Schedule lessons error: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        conn.close()