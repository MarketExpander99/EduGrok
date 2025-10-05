# lesson_routes.py (Replace this ENTIRE file—old version has "Added lesson X" content; new one uses title + desc for interactive card. Added flash/alert for confirmation.)
from flask import session, request, jsonify, redirect, url_for, render_template, flash
import logging
from datetime import datetime, timedelta
from db import get_db
import random

logger = logging.getLogger(__name__)

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.json
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    if not all([lesson_id, activity_type, response]):
        return jsonify({'success': False, 'error': 'Missing data'}), 400
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
        complete_lesson(lesson_id)
    return jsonify({'success': True, 'is_correct': is_correct, 'points': points})

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)", (session['user_id'], lesson_id, datetime.now().isoformat()))
    conn.commit()
    flash('Lesson completed!', 'success')
    return redirect(url_for('lessons'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
    c.execute("DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
    conn.commit()
    flash('Lesson reset!', 'success')
    return redirect(url_for('lessons'))

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    grade = session.get('grade', 1)
    c.execute("SELECT * FROM lessons WHERE grade = ? ORDER BY created_at DESC", (grade,))
    lessons_list = c.fetchall()
    c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (session['user_id'],))
    completed_ids = [row['lesson_id'] for row in c.fetchall()]
    theme = session.get('theme', 'astronaut')
    language = session.get('language', 'en')
    return render_template('lessons.html.j2', lessons=lessons_list, completed_ids=completed_ids, theme=theme, language=language)

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    grade = session.get('grade', 1)
    subjects = ['math', 'language', 'science', 'social_studies']
    subject = random.choice(subjects)
    title = f"Generated Lesson for Grade {grade} - {subject.capitalize()}"
    description = f"This is a generated {subject} lesson for grade {grade}. Practice makes perfect!"
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO lessons (title, grade, subject, description, created_at) VALUES (?, ?, ?, ?, ?)", (title, grade, subject, description, datetime.now().isoformat()))
    conn.commit()
    return jsonify({'success': True})

def schedule_lessons():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    conn = get_db()
    c = conn.cursor()
    grade = session.get('grade', 1)
    c.execute("SELECT id FROM lessons WHERE grade = ? ORDER BY RANDOM() LIMIT 5", (grade,))
    lesson_ids = [row['id'] for row in c.fetchall()]
    now = datetime.now()
    for i, lesson_id in enumerate(lesson_ids):
        assigned_at = (now + timedelta(days=i)).isoformat()
        c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)", (session['user_id'], lesson_id, assigned_at))
    conn.commit()
    return jsonify({'success': True})

def add_to_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.json
    lesson_id = data.get('lesson_id')
    if not lesson_id:
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    lesson = c.fetchone()
    if not lesson:
        return jsonify({'success': False, 'error': 'Lesson not found'}), 404
    # FIXED: This is the key line—uses lesson title + description for content, so feed shows interactive card, not notification
    content = f"Lesson: {lesson['title']}\n{lesson['description']}"
    handle = session.get('handle', session.get('email', 'User'))
    logger.info(f"Adding lesson post: type='lesson', id={lesson_id}, title={lesson['title'][:30]} for user {session['user_id']}")
    c.execute("""INSERT INTO posts (user_id, content, created_at, subject, grade, handle, type, lesson_id) 
                 VALUES (?, ?, ?, ?, ?, ?, 'lesson', ?)""", 
              (session['user_id'], content, datetime.now().isoformat(), lesson['subject'], lesson['grade'], handle, lesson_id))
    post_id = c.lastrowid
    conn.commit()
    logger.info(f"Lesson post inserted: ID={post_id}, type=lesson")
    flash('Interactive lesson added to feed!')  # Confirmation
    return jsonify({'success': True, 'post_id': post_id})