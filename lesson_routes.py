# lesson_routes.py (Fixed: In add_to_feed, removed SELECT check and used INSERT directly; catch IntegrityError for unique violation to return 'Already in feed'. This prevents duplicates even on multiple rapid clicks. Preserved all other logic.)
from flask import session, request, jsonify, redirect, url_for, render_template, flash
import logging
from datetime import datetime
import json
import sqlite3

logger = logging.getLogger(__name__)

from db import get_db

def lessons():
    logger.debug("Lessons route accessed")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    # Fetch user's grade-specific lessons
    grade = session.get('grade', 1)
    c.execute("SELECT * FROM lessons WHERE grade = ? ORDER BY created_at DESC", (grade,))
    all_lessons = c.fetchall()
    # Fetch assigned lessons (now with completed=0 filter, column added in schema)
    c.execute("""SELECT l.* FROM lessons l
                 JOIN lessons_users lu ON l.id = lu.lesson_id
                 WHERE lu.user_id = ? AND lu.completed = 0""", (session['user_id'],))
    assigned_lessons = c.fetchall()
    # Fetch completed lessons
    c.execute("""SELECT l.* FROM lessons l
                 JOIN completed_lessons cl ON l.id = cl.lesson_id
                 WHERE cl.user_id = ?""", (session['user_id'],))
    completed_lessons = c.fetchall()
    # Also fetch completed_ids for template compatibility
    c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (session['user_id'],))
    completed_ids = [row['lesson_id'] for row in c.fetchall()]
    # NEW: Fetch added lesson IDs (global lesson posts)
    c.execute("SELECT DISTINCT lesson_id FROM posts WHERE type = 'lesson' AND lesson_id IS NOT NULL")
    added_ids = [row['lesson_id'] for row in c.fetchall()]
    conn.close()
    return render_template('lessons.html.j2',
                           all_lessons=all_lessons,
                           assigned_lessons=assigned_lessons,
                           completed_lessons=completed_lessons,
                           lessons=all_lessons,  # For original template
                           completed_ids=completed_ids,
                           added_ids=added_ids,  # For button state
                           theme=session.get('theme', 'astronaut'),
                           language=session.get('language', 'en'))

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    if request.method == 'POST':
        grade = session.get('grade', 1)
        subject = request.form.get('subject', 'math')
        # Simulate generation (in real, call AI API)
        title = f"Generated {subject} Lesson for Grade {grade}"
        content = f"Generated content for {subject}..."
        now = datetime.now().isoformat()
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO lessons (title, grade, subject, content, description, created_at)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (title, grade, subject, content, f"Auto-generated {subject} lesson", now))
        lesson_id = c.lastrowid
        conn.commit()
        conn.close()
        flash('Lesson generated successfully!', 'success')
        return redirect(url_for('lessons'))
    return redirect(url_for('lessons'))

def schedule_lessons():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    if request.method == 'POST':
        lesson_ids = request.form.getlist('lesson_ids[]')
        conn = get_db()
        c = conn.cursor()
        now = datetime.now().isoformat()
        for lesson_id in lesson_ids:
            # Check if already assigned
            c.execute("SELECT id FROM lessons_users WHERE user_id=? AND lesson_id=?", (session['user_id'], lesson_id))
            if not c.fetchone():
                c.execute("INSERT INTO lessons_users (user_id, lesson_id, assigned_at, completed) VALUES (?, ?, ?, 0)",
                          (session['user_id'], lesson_id, now))
        conn.commit()
        conn.close()
        flash(f'{len(lesson_ids)} lessons scheduled!', 'success')
        return redirect(url_for('lessons'))
    return redirect(url_for('lessons'))

def add_to_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    if request.method == 'POST':
        data = request.get_json()
        lesson_id = data.get('lesson_id')
        if not lesson_id:
            return jsonify({'success': False, 'error': 'No lesson ID provided'}), 400
        try:
            conn = get_db()
            c = conn.cursor()
            # Fetch lesson details
            c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
            lesson = c.fetchone()
            if not lesson:
                return jsonify({'success': False, 'error': 'Lesson not found'}), 404
            # FIXED: Attempt insert; catch IntegrityError from unique index to detect duplicate
            now = datetime.now().isoformat()
            content = f"Lesson: {lesson['title']}\n{lesson['description']}"
            c.execute("""INSERT INTO posts (user_id, content, created_at, subject, grade, handle, type, lesson_id)
                         VALUES (NULL, ?, ?, ?, ?, 'EduGrok', 'lesson', ?)""",
                      (content,
                       now,
                       lesson['subject'],
                       lesson['grade'],
                       lesson_id))
            post_id = c.lastrowid
            conn.commit()
            logger.info(f"Added global lesson post {post_id} for lesson {lesson_id}")
            return jsonify({'success': True, 'post_id': post_id})
        except sqlite3.IntegrityError:
            logger.info(f"Lesson {lesson_id} already in global feed (unique constraint)")
            return jsonify({'success': True, 'message': 'Already in feed'})
        except Exception as e:
            logger.error(f"Error adding lesson to feed: {str(e)}")
            return jsonify({'success': False, 'error': 'Server error'}), 500
        finally:
            if conn:
                conn.close()
    return jsonify({'success': False, 'error': 'Invalid request'}), 400

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.json
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    if not all([lesson_id, activity_type, response]):
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        is_correct = 0
        points = 0
        if activity_type == 'trace':
            is_correct = 1
            points = 5
        elif activity_type == 'spell':
            is_correct = response.lower() == lesson['spell_word'].lower() if lesson['spell_word'] else 0
            points = 10 if is_correct else 0
        elif activity_type == 'sound':
            is_correct = response.lower() == lesson['sound'].lower() if lesson['sound'] else 0
            points = 10 if is_correct else 0
        elif activity_type == 'mc':
            is_correct = response == lesson['mc_answer'] if lesson['mc_answer'] else 0
            points = 15 if is_correct else 0
        elif activity_type == 'sentence':
            is_correct = response == lesson['sentence_answer'] if lesson['sentence_answer'] else 0
            points = 15 if is_correct else 0
        elif activity_type == 'math':
            is_correct = response == lesson['math_answer'] if lesson['math_answer'] else 0
            points = 15 if is_correct else 0
        c.execute("INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, points) VALUES (?, ?, ?, ?, ?, ?)",
                  (lesson_id, session['user_id'], activity_type, response, is_correct, points))
        conn.commit()
        c.execute("SELECT COUNT(DISTINCT activity_type) FROM lesson_responses WHERE lesson_id = ? AND user_id = ? AND is_correct = 1", (lesson_id, session['user_id']))
        completed_activities = c.fetchone()[0]
        total_activities = sum(1 for field in ['trace_word', 'spell_word', 'sound', 'mc_question', 'sentence_question', 'math_question'] if lesson[field])
        if completed_activities >= total_activities:
            # Call complete_lesson logic
            now = datetime.now().isoformat()
            c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)",
                      (session['user_id'], lesson_id, now))
            c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?",
                      (session['user_id'], lesson_id))
            conn.commit()
        logger.info(f"Lesson check success: user={session['user_id']}, lesson={lesson_id}, type={activity_type}, correct={is_correct}, points={points}")
        return jsonify({'success': True, 'is_correct': is_correct, 'points': points})
    except Exception as e:
        logger.error(f"Lesson check error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    # Mark as completed
    c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)",
              (session['user_id'], lesson_id, now))
    # Mark assigned as completed
    c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?",
              (session['user_id'], lesson_id))
    conn.commit()
    conn.close()
    flash('Lesson completed!', 'success')
    return redirect(url_for('lessons'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    # Remove from completed
    c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?",
              (session['user_id'], lesson_id))
    # Reset assigned
    c.execute("UPDATE lessons_users SET completed = 0 WHERE user_id = ? AND lesson_id = ?",
              (session['user_id'], lesson_id))
    # Also reset responses
    c.execute("DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?",
              (session['user_id'], lesson_id))
    conn.commit()
    conn.close()
    flash('Lesson reset!', 'info')
    return redirect(url_for('lessons'))