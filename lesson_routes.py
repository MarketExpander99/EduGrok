# [lesson_routes.py]
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
    lessons_raw = c.fetchall()
    lessons_list = []
    for row in lessons_raw:
        lesson_dict = dict(row)
        # Parse JSON fields to lists
        if lesson_dict.get('mc_options'):
            try:
                lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options'])
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in mc_options for lesson {lesson_dict['id']}: {e}")
                lesson_dict['mc_options'] = []
        if lesson_dict.get('sentence_options'):
            try:
                lesson_dict['sentence_options'] = json.loads(lesson_dict['sentence_options'])
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in sentence_options for lesson {lesson_dict['id']}: {e}")
                lesson_dict['sentence_options'] = []
        lessons_list.append(lesson_dict)
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

def add_to_feed():
    if 'user_id' not in session:
        logger.warning("Add to feed unauthorized")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    user_id = session['user_id']
    logger.info(f"Add to feed attempt: user {user_id}, lesson {lesson_id}")
    if not lesson_id:
        logger.warning(f"Missing lesson_id for user {user_id}")
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        # Check if already added by this user
        c.execute("SELECT id FROM posts WHERE user_id = ? AND lesson_id = ? AND type = 'lesson'", (user_id, lesson_id))
        if c.fetchone():
            logger.info(f"Lesson {lesson_id} already in feed for user {user_id}")
            return jsonify({'success': False, 'message': 'Already in feed'})
        # Get lesson
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson_row = c.fetchone()
        if not lesson_row:
            logger.warning(f"Lesson {lesson_id} not found")
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        lesson = dict(lesson_row)
        # Validate grade
        user_grade = session.get('grade', 1)
        if lesson['grade'] != user_grade:
            logger.warning(f"Grade mismatch: lesson {lesson['grade']} != user {user_grade} for lesson {lesson_id}")
            return jsonify({'success': False, 'error': 'Grade mismatch'}), 400
        logger.info(f"Grade check passed: {user_grade} for lesson {lesson_id}")
        # Insert post
        now = datetime.now().isoformat()
        c.execute("""INSERT INTO posts 
                     (user_id, content, subject, grade, handle, type, lesson_id, created_at, views, likes, reposts) 
                     VALUES (?, ?, ?, ?, ?, 'lesson', ?, ?, 0, 0, 0)""", 
                  (user_id, lesson['title'], lesson['subject'], lesson['grade'], 
                   session.get('handle', session.get('email', 'User')), lesson_id, now))
        post_id = c.lastrowid
        conn.commit()
        logger.info(f"Lesson {lesson_id} added to feed as post {post_id} for user {user_id}")
        return jsonify({'success': True, 'message': 'Added to feed!'})
    except sqlite3.IntegrityError as e:
        logger.warning(f"Add to feed integrity error for user {user_id}, lesson {lesson_id}: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Already exists'}), 409
    except Exception as e:
        logger.error(f"Add to feed error for user {user_id}, lesson {lesson_id}: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    user_answer = data.get('answer')
    if not lesson_id or not activity_type or not user_answer:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT trace_word, spell_word, mc_answer, sentence_answer, math_answer FROM lessons WHERE id = ?", (lesson_id,))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        # Select correct answer based on activity_type
        answer_map = {
            'trace': 'trace_word',
            'spell': 'spell_word',
            'mc': 'mc_answer',
            'sentence': 'sentence_answer',
            'math': 'math_answer'
        }
        if activity_type not in answer_map:
            return jsonify({'success': False, 'error': 'Invalid activity type'}), 400
        correct_answer = lesson[answer_map[activity_type]]
        if not correct_answer:
            return jsonify({'success': False, 'error': f'No answer defined for {activity_type}'}), 404
        # Normalize answers
        try:
            correct_answer = json.loads(correct_answer) if isinstance(correct_answer, str) else correct_answer
        except json.JSONDecodeError:
            correct_answer = correct_answer
        user_answer = str(user_answer).strip().lower()
        correct_answer = [str(c).strip().lower() for c in (correct_answer if isinstance(correct_answer, list) else [correct_answer])]
        # Compare answers
        is_correct = user_answer in correct_answer
        points = 10 if is_correct else 0
        now = datetime.now().isoformat()
        # FIXED: Use UPSERT to update if already exists for this activity
        c.execute("""INSERT OR REPLACE INTO activity_responses 
                     (id, lesson_id, user_id, activity_type, response, is_correct, points, responded_at) 
                     VALUES (
                         (SELECT id FROM activity_responses WHERE lesson_id = ? AND user_id = ? AND activity_type = ?),
                         ?, ?, ?, ?, ?, ?, ?
                     )""", 
                  (lesson_id, session['user_id'], activity_type, lesson_id, session['user_id'], activity_type, user_answer, is_correct, points, now))
        # FIXED: Properly determine required_activities based on non-null answer fields
        activity_types = {
            'trace': lesson['trace_word'] is not None,
            'spell': lesson['spell_word'] is not None,
            'mc': lesson['mc_answer'] is not None,
            'sentence': lesson['sentence_answer'] is not None,
            'math': lesson['math_answer'] is not None
        }
        required_activities = {k for k, v in activity_types.items() if v}
        c.execute("SELECT activity_type FROM activity_responses WHERE lesson_id = ? AND user_id = ? AND is_correct = 1", 
                  (lesson_id, session['user_id']))
        completed_activities = {row['activity_type'] for row in c.fetchall()}
        logger.info(f"Lesson {lesson_id}, user {session['user_id']}: required_activities={required_activities}, completed_activities={completed_activities}")
        lesson_completed = required_activities.issubset(completed_activities)
        if lesson_completed:
            c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at, parent_confirmed) VALUES (?, ?, ?, 0)", 
                      (session['user_id'], lesson_id, now))
            c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                      (session['user_id'], lesson_id))
        conn.commit()
        return jsonify({
            'success': True, 
            'correct': bool(is_correct), 
            'points': points, 
            'message': 'Correct!' if is_correct else 'Incorrect, try again.',
            'lesson_completed': lesson_completed
        })
    except Exception as e:
        logger.error(f"Check lesson error: {e}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        now = datetime.now().isoformat()
        c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at, parent_confirmed) VALUES (?, ?, ?, 0)", 
                  (session['user_id'], lesson_id, now))
        c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson completed successfully!', 'success')
    except Exception as e:
        logger.error(f"Complete lesson error: {e}")
        conn.rollback()
        flash('Error completing lesson', 'error')
    finally:
        conn.close()
    return redirect(url_for('lessons'))

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
        c.execute("DELETE FROM activity_responses WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson reset successfully!', 'success')
    except Exception as e:
        logger.error(f"Reset lesson error: {e}")
        conn.rollback()
        flash('Error resetting lesson', 'error')
    finally:
        conn.close()
    return redirect(url_for('lessons'))

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