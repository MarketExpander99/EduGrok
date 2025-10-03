# lesson_routes.py
import json
from flask import session, request, flash, redirect, url_for, jsonify, render_template
from db import get_db
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def check_lesson():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        data = request.get_json()
        lesson_id = data.get('lesson_id')
        activity_type = data.get('activity_type')
        user_input = data.get('response')
        if not lesson_id or not activity_type or user_input is None:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        conn = get_db()
        c = conn.cursor()
        success = False
        correct_answer = None
        points = 10
        if activity_type == 'math_fill':
            c.execute("SELECT math_answer FROM lessons WHERE id = ?", (lesson_id,))
            result = c.fetchone()
            if result:
                correct_answer = result['math_answer']
                success = str(user_input).strip() == str(correct_answer).strip()
        elif activity_type == 'trace_complete':
            c.execute("SELECT trace_word FROM lessons WHERE id = ?", (lesson_id,))
            result = c.fetchone()
            if result:
                correct_answer = result['trace_word']
                success = str(user_input).strip().lower() == str(correct_answer).lower()
        elif activity_type == 'spelling_complete':
            c.execute("SELECT spell_word FROM lessons WHERE id = ?", (lesson_id,))
            result = c.fetchone()
            if result:
                correct_answer = result['spell_word']
                success = str(user_input).strip().lower() == str(correct_answer).lower()
        elif activity_type == 'mc_choice':
            c.execute("SELECT mc_answer FROM lessons WHERE id = ?", (lesson_id,))
            result = c.fetchone()
            if result:
                correct_answer = result['mc_answer']
                success = str(user_input).strip().lower() == str(correct_answer).lower()
        elif activity_type == 'sentence_complete':
            c.execute("SELECT sentence_answer FROM lessons WHERE id = ?", (lesson_id,))
            result = c.fetchone()
            if result:
                correct_answer = result['sentence_answer']
                success = str(user_input).strip().lower() == str(correct_answer).lower()
        else:
            return jsonify({'success': False, 'error': 'Invalid activity type'}), 400
        
        if not correct_answer:
            return jsonify({'success': False, 'error': 'Lesson or activity not found'}), 404
        
        message = 'Correct!' if success else 'Try again.'
        if success:
            # Insert response
            c.execute('''INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, points) 
                         VALUES (?, ?, ?, ?, 1, ?)''', (lesson_id, session['user_id'], activity_type, user_input, points))
            # Award points
            c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, ?, ?)",
                      (session['user_id'], points, datetime.now().isoformat()))
            conn.commit()
            return jsonify({'success': True, 'is_correct': True, 'message': message, 'points': points})
        else:
            # Log incorrect response
            c.execute('''INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, points) 
                         VALUES (?, ?, ?, ?, 0, 0)''', (lesson_id, session['user_id'], activity_type, user_input))
            conn.commit()
            return jsonify({'success': True, 'is_correct': False, 'message': message})
    return jsonify({'success': False, 'error': 'Invalid method'}), 405

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)",
              (session['user_id'], lesson_id, datetime.now().isoformat()))
    conn.commit()
    flash('Lesson completed!', 'success')
    return redirect(url_for('home'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
    conn.commit()
    flash('Lesson reset!', 'success')
    return redirect(url_for('home'))

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM lessons WHERE grade = ?", (session.get('grade', 1),))
    raw_lessons = c.fetchall()
    lessons = []
    for row in raw_lessons:
        lesson = dict(row)
        if lesson['mc_options']:
            try:
                lesson['mc_options'] = json.loads(lesson['mc_options'])
            except json.JSONDecodeError:
                lesson['mc_options'] = []
        if lesson['sentence_options']:
            try:
                lesson['sentence_options'] = json.loads(lesson['sentence_options'])
            except json.JSONDecodeError:
                lesson['sentence_options'] = []
        c.execute("SELECT 1 FROM lessons_users WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson['id']))
        lesson['added'] = bool(c.fetchone())
        c.execute("SELECT 1 FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson['id']))
        lesson['completed'] = bool(c.fetchone())
        lessons.append(lesson)
    return render_template('lessons.html.j2', lessons=lessons, grade=session.get('grade', 1), theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def generate_lesson():
    # Placeholder for generating lessons, perhaps using AI
    return jsonify({'success': False, 'error': 'Not implemented'})

def schedule_lessons():
    # Placeholder
    return jsonify({'success': False, 'error': 'Not implemented'})

def add_to_feed():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        data = request.get_json()
        lesson_id = data.get('lesson_id')
        if not lesson_id:
            return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)",
                      (session['user_id'], lesson_id, datetime.now().isoformat()))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Add to feed failed: {str(e)}")
            return jsonify({'success': False, 'error': 'Server error'}), 500
    return jsonify({'success': False, 'error': 'Invalid method'}), 405