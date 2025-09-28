# lesson_routes.py
from flask import render_template, session, request, jsonify, flash, redirect, url_for, current_app
import json
import logging
from db import get_db

logger = logging.getLogger(__name__)

def check_lesson():
    logger.debug("Checking lesson")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    # Safe string conversion and normalization
    if isinstance(response, (int, float)):
        response = str(response).strip().lower()
    elif isinstance(response, str):
        response = response.strip().lower()
    else:
        response = str(response or '').strip().lower()
    complete_lesson = data.get('complete_lesson', False)

    if not lesson_id or not activity_type:
        return jsonify({'success': False, 'error': 'Missing lesson_id or activity_type'}), 400

    try:
        conn = get_db()
        c = conn.cursor()

        # Fetch lesson
        c.execute('SELECT * FROM lessons WHERE id = ? AND user_id = ? AND completed = 0', 
                  (lesson_id, session['user_id']))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found or already completed'}), 404

        # Determine expected answer based on activity_type
        expected = ''
        if activity_type == 'trace_complete':
            expected = (lesson['trace_word'] or '').strip().lower()
        elif activity_type == 'spelling_complete':
            expected = (lesson['spell_word'] or '').strip().lower()
        elif activity_type == 'mc_choice':
            expected = (lesson['mc_answer'] or '').strip().lower()
            # Optional: Handle mc_options as list if comma-separated (for array-like checks)
            # mc_opts = [opt.strip().lower() for opt in (lesson['mc_options'] or '').split(',') if opt.strip()]
            # if response in mc_opts:  # If multi-correct, but keep == for now
        elif activity_type == 'sentence_complete':
            expected = (lesson['sentence_answer'] or 'mat').strip().lower()  # Dynamic fallback
        elif activity_type == 'math_fill':
            expected = (lesson['math_answer'] or '6').strip().lower()  # Dynamic fallback
        elif activity_type == 'match_game':
            expected = f"demo_match_{lesson_id}"  # Dynamic stub based on ID

        is_correct = (response == expected)
        points = 10 if is_correct else 0

        # Save response to DB
        c.execute('''INSERT INTO lesson_responses 
                     (lesson_id, user_id, activity_type, response, is_correct, points)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (lesson_id, session['user_id'], activity_type, response, is_correct, points))
        conn.commit()

        logger.info(f"Lesson {lesson_id} activity {activity_type} for user {session['user_id']}: {'Correct' if is_correct else 'Incorrect'} (response: {response} (type: {type(response)}), expected: {expected} (type: {type(expected)}))")

        if complete_lesson:
            # Mark lesson as completed and award bonus points
            total_points = 50  # Base completion points; adjust as needed
            c.execute('UPDATE lessons SET completed = 1 WHERE id = ?', (lesson_id,))
            c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (total_points, session['user_id']))
            conn.commit()
            points += total_points  # Add to response points
            logger.info(f"Completed lesson {lesson_id} for user {session['user_id']}, awarded {total_points} coins")

        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'points': points,
            'message': 'Correct!' if is_correct else 'Try again!'
        })

    except Exception as e:
        logger.error(f"Check lesson failed for lesson {lesson_id}: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('lessons'))

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE lessons SET completed = 1 WHERE id = ? AND user_id = ?', 
                  (lesson_id, session['user_id']))
        if c.rowcount == 0:
            flash('Lesson not found or already completed', 'error')
            return redirect(url_for('lessons'))

        # Award points
        points = 50
        c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (points, session['user_id']))
        conn.commit()
        flash(f'Lesson completed! +{points} star coins', 'success')
        logger.info(f"Manually completed lesson {lesson_id} for user {session['user_id']}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('lessons'))

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE lessons SET completed = 0 WHERE id = ? AND user_id = ?', 
                  (lesson_id, session['user_id']))
        if c.rowcount == 0:
            flash('Lesson not found', 'error')
            return redirect(url_for('lessons'))

        # Reset responses
        c.execute('DELETE FROM lesson_responses WHERE lesson_id = ?', (lesson_id,))
        conn.commit()
        flash('Lesson reset successfully', 'success')
        logger.info(f"Reset lesson {lesson_id} for user {session['user_id']}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db()
        c = conn.cursor()
        grade = session.get('grade', 1)
        c.execute('SELECT * FROM lessons WHERE user_id = ? AND grade = ? ORDER BY id DESC', 
                  (session['user_id'], grade))
        lessons_list = c.fetchall()
        return render_template('lessons.html.j2', lessons=lessons_list, grade=grade)
    except Exception as e:
        logger.error(f"Fetch lessons failed: {str(e)}")
        flash('Server error', 'error')
        return redirect(url_for('home'))

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.json
    subject = data.get('subject', 'language')
    grade = session.get('grade', 1)

    # Simple generation logic; in production, use AI or predefined
    trace_word = None
    spell_word = None
    sound = None
    mc_question = None
    mc_options = None
    mc_answer = None
    content = ''
    math_answer = None
    sentence_answer = None

    if subject == 'language':
        trace_word = 'sun'
        spell_word = 'sun'
        sound = '/sʌn/'
        mc_question = 'What is the correct spelling?'
        mc_options = 'sun,son,sunne'  # Comma-separated
        mc_answer = 'sun'
        sentence_answer = 'mat'
        content = f"Learn the {sound} sound with words like sun and star."
    elif subject == 'math':
        # Simple dynamic math: e.g., 2+4
        a, b, op = 2, 4, '+'
        expression = f"{a}{op}{b}"
        content = f"What is {expression}?"
        math_answer = str(eval(f"{a}{op}{b}"))  # Safe eval for simple ops
        # For variety, randomize: import random; a=random.randint(1,10); etc.

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO lessons (user_id, grade, subject, content, trace_word, sound, spell_word, 
                     mc_question, mc_options, mc_answer, math_answer, sentence_answer) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (session['user_id'], grade, subject, content, trace_word, sound, spell_word,
                   mc_question, mc_options, mc_answer, math_answer, sentence_answer))
        conn.commit()
        lesson_id = c.lastrowid
        logger.info(f"Generated lesson {lesson_id} for user {session['user_id']}")
        return jsonify({'success': True, 'lesson_id': lesson_id})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500