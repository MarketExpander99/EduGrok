# lesson_routes.py
from flask import session, request, jsonify, render_template, redirect, url_for, flash
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

from db import get_db

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    if not all([lesson_id, activity_type, response]):
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        # FIXED: Use dynamic column based on activity_type, with safe fallback
        col = f"{activity_type}_answer"
        c.execute(f"SELECT {col} FROM lessons WHERE id = ?", (lesson_id,))
        row = c.fetchone()
        if not row or row[0] is None:
            return jsonify({'success': False, 'error': 'Invalid activity type'}), 400
        correct_answer = row[0]
        is_correct = response == correct_answer
        points = 5 if is_correct else 0
        c.execute("INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, points, responded_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                  (lesson_id, session['user_id'], activity_type, response, int(is_correct), points))
        conn.commit()
        logger.info(f"User {session['user_id']} responded to {activity_type} in lesson {lesson_id}, correct: {is_correct}")
        return jsonify({'success': True, 'is_correct': is_correct, 'points': points})
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        now = datetime.now().isoformat()
        # FIXED: Use isoformat for consistency
        c.execute("INSERT INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)", (session['user_id'], lesson_id, now))
        c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, 10, ?)", (session['user_id'], now))
        conn.commit()
        flash('Lesson completed! +10 points', 'success')
        logger.info(f"User {session['user_id']} completed lesson {lesson_id}")
        return redirect(url_for('home'))  # FIXED: Redirect to home to see updated feed
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))
    finally:
        if conn:
            conn.close()

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
        c.execute("DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson reset', 'success')
        logger.info(f"User {session['user_id']} reset lesson {lesson_id}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))
    finally:
        if conn:
            conn.close()

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        grade = session.get('grade', 1)
        c.execute("SELECT * FROM lessons WHERE grade = ? ORDER BY id ASC", (grade,))
        lessons = c.fetchall()
        c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (session['user_id'],))
        completed_lessons = [row['lesson_id'] for row in c.fetchall()]
        # NEW: Fetch assigned_lessons for added_lessons
        c.execute("SELECT lesson_id FROM lessons_users WHERE user_id = ?", (session['user_id'],))
        added_lessons = [row['lesson_id'] for row in c.fetchall()]
        logger.info(f"User {session['user_id']} accessed lessons, {len(lessons)} available")
        return render_template('lessons.html.j2', 
                               lessons=lessons, 
                               completed_lessons=completed_lessons, 
                               added_lessons=added_lessons,
                               theme=session.get('theme', 'astronaut'), 
                               language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Lessons route failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Error loading lessons', 'error')
        return redirect(url_for('home'))
    finally:
        if conn:
            conn.close()

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        grade = session.get('grade', 1)
        now = datetime.now().isoformat()
        # FIXED: Query DB count instead of calling route function
        c.execute("SELECT COUNT(*) FROM lessons WHERE grade = ?", (grade,))
        count = c.fetchone()[0]
        title = f"Generated Lesson {count + 1} for Grade {grade}"
        content = "Generated content with interactive activities."
        description = "This is a dynamically generated lesson based on your grade level."
        subject = 'math'  # Or randomize: random.choice(['math', 'language', 'science'])
        c.execute('''INSERT INTO lessons (title, grade, subject, content, description, created_at) 
                     VALUES (?, ?, ?, ?, ?, ?)''', (title, grade, subject, content, description, now))
        lesson_id = c.lastrowid
        conn.commit()
        logger.info(f"Generated lesson {lesson_id} for user {session['user_id']}")
        return jsonify({'success': True, 'lesson_id': lesson_id})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def add_to_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    if not lesson_id:
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM lessons_users WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Already added to feed'}), 400
        now = datetime.now().isoformat()
        c.execute("INSERT INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)", (session['user_id'], lesson_id, now))
        conn.commit()
        logger.info(f"Lesson {lesson_id} added to feed (assigned) for user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Add to feed failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def schedule_lessons():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        grade = session.get('grade', 1)
        c.execute("SELECT id FROM lessons WHERE grade = ?", (grade,))
        lesson_ids = [row['id'] for row in c.fetchall()]
        now = datetime.now().isoformat()
        values = [(session['user_id'], lid, now) for lid in lesson_ids]
        c.executemany("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)", values)
        conn.commit()
        logger.info(f"Scheduled {len(lesson_ids)} lessons for user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Schedule lessons failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500