# lesson_routes.py
from flask import session, request, flash, redirect, url_for, jsonify
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
        user_input = data.get('user_input')
        if not lesson_id or user_input is None:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT type, correct_answer FROM lessons WHERE id = ?", (lesson_id,))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        correct_answer = lesson['correct_answer']
        lesson_type = lesson['type']
        success = False
        if lesson_type in ['trace', 'spelling', 'sentence']:
            success = user_input.strip().lower() == correct_answer.lower()
        elif lesson_type == 'multiple_choice':
            success = user_input == correct_answer
        message = 'Correct!' if success else 'Try again.'
        if success:
            c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, 10, ?)",
                      (session['user_id'], datetime.now().isoformat()))
            conn.commit()
        return jsonify({'success': success, 'message': message})
    return jsonify({'success': False, 'error': 'Invalid method'}), 405

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO user_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)",
              (session['user_id'], lesson_id, datetime.now().isoformat()))
    conn.commit()
    flash('Lesson completed!', 'success')
    return redirect(url_for('home'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM user_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
    conn.commit()
    flash('Lesson reset!', 'success')
    return redirect(url_for('home'))

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM lessons")
    lessons = [dict(row) for row in c.fetchall()]
    return render_template('lessons.html.j2', lessons=lessons, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def generate_lesson():
    # Placeholder for generating lessons, perhaps using AI
    return jsonify({'success': False, 'error': 'Not implemented'})

def schedule_lessons():
    # Placeholder
    return jsonify({'success': False, 'error': 'Not implemented'})

def add_to_feed():
    # Placeholder
    return jsonify({'success': False, 'error': 'Not implemented'})