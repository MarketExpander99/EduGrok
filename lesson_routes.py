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

    if not lesson_id:
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400

    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()

        # Auto-assign if not already
        c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id) VALUES (?, ?)", (user_id, lesson_id))
        conn.commit()

        # Fetch lesson (ensure assigned and incomplete)
        c.execute("""
            SELECT l.* FROM lessons l 
            JOIN lessons_users lu ON l.id = lu.lesson_id 
            WHERE lu.user_id = ? AND l.id = ? AND lu.completed = 0
        """, (user_id, lesson_id))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found or already completed'}), 404

        is_correct = False
        points = 0
        if activity_type:
            # Determine expected answer based on activity_type
            expected = ''
            if activity_type == 'trace_complete':
                expected = (lesson['trace_word'] or '').strip().lower()
            elif activity_type == 'spelling_complete':
                expected = (lesson['spell_word'] or '').strip().lower()
            elif activity_type == 'mc_choice':
                expected = (lesson['mc_answer'] or '').strip().lower()
            elif activity_type == 'sentence_complete':
                expected = (lesson['sentence_answer'] or 'mat').strip().lower()  # Fixed: fallback to 'mat' to match template options
            elif activity_type == 'math_fill':
                expected = (lesson['math_answer'] or '').strip().lower()
            elif activity_type == 'match_game':
                expected = f"demo_match_{lesson_id}"

            is_correct = (response == expected)
            points = 10 if is_correct else 0

            # Save response to DB
            c.execute('''INSERT INTO lesson_responses 
                         (lesson_id, user_id, activity_type, response, is_correct, points)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (lesson_id, user_id, activity_type, response, is_correct, points))
            conn.commit()

            logger.info(f"Lesson {lesson_id} activity {activity_type} for user {user_id}: {'Correct' if is_correct else 'Incorrect'} (response: {response} (type: {type(response)}), expected: {expected} (type: {type(expected)}))")

        if complete_lesson:
            # Mark assignment as completed and award bonus points
            c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", (user_id, lesson_id))
            if c.rowcount > 0:
                total_points = 50
                c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (total_points, user_id))
                conn.commit()
                points += total_points
                logger.info(f"Completed lesson {lesson_id} for user {user_id}, awarded {total_points} coins")
            else:
                logger.warning(f"No rows updated for complete lesson {lesson_id} user {user_id}")

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

    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                  (user_id, lesson_id))
        if c.rowcount == 0:
            flash('Lesson not found or already completed', 'error')
            return redirect(url_for('lessons'))

        # Award points
        points = 50
        c.execute('UPDATE users SET star_coins = star_coins + ? WHERE id = ?', (points, user_id))
        conn.commit()
        flash(f'Lesson completed! +{points} star coins', 'success')
        logger.info(f"Manually completed lesson {lesson_id} for user {user_id}")
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

    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE lessons_users SET completed = 0 WHERE user_id = ? AND lesson_id = ?', 
                  (user_id, lesson_id))
        if c.rowcount == 0:
            flash('Lesson not found', 'error')
            return redirect(url_for('lessons'))

        # Reset responses
        c.execute('DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?', (user_id, lesson_id))
        conn.commit()
        flash('Lesson reset! It\'s back in your feed.', 'success')
        logger.info(f"Reset lesson {lesson_id} for user {user_id}")
        return redirect(url_for('home'))  # Changed: Redirect to home/feed
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('lessons'))

    user_id = session['user_id']
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE lessons_users SET completed = 0 WHERE user_id = ? AND lesson_id = ?', 
                  (user_id, lesson_id))
        if c.rowcount == 0:
            flash('Lesson not found', 'error')
            return redirect(url_for('lessons'))

        # Reset responses
        c.execute('DELETE FROM lesson_responses WHERE user_id = ? AND lesson_id = ?', (user_id, lesson_id))
        conn.commit()
        flash('Lesson reset successfully', 'success')
        logger.info(f"Reset lesson {lesson_id} for user {user_id}")
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
        user_id = session['user_id']

        # Fetch ALL lessons for grade, LEFT JOIN to get completed status (NULL if unassigned)
        c.execute("""
            SELECT l.*, lu.completed 
            FROM lessons l 
            LEFT JOIN lessons_users lu ON (l.id = lu.lesson_id AND lu.user_id = ?)
            WHERE l.grade = ?
            ORDER BY l.id ASC
        """, (user_id, grade))
        raw_lessons = c.fetchall()
        lessons_list = []
        unassigned_ids = []

        for r in raw_lessons:
            lesson_dict = dict(r)
            original_completed = lesson_dict.get('completed')  # Capture before change
            if lesson_dict.get('mc_options'):
                lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options'])
            # Treat NULL completed as 0 (incomplete/unassigned)
            lesson_dict['completed'] = lesson_dict['completed'] or 0
            lessons_list.append(lesson_dict)
            # Append ONLY if originally unassigned (None)
            if original_completed is None:
                unassigned_ids.append(lesson_dict['id'])

        # Auto-assign any unassigned ones (all at once, no limit)
        if unassigned_ids:
            c.executemany("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, completed) VALUES (?, ?, 0)", 
                          [(user_id, lid) for lid in unassigned_ids])
            conn.commit()
            logger.info(f"Auto-assigned {len(unassigned_ids)} lessons for user {user_id} in grade {grade}")

        return render_template('lessons.html.j2', lessons=lessons_list, grade=grade)
    except Exception as e:
        logger.error(f"Fetch lessons failed: {str(e)}")
        flash('Server error', 'error')
        return redirect(url_for('home'))
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db()
        c = conn.cursor()
        grade = session.get('grade', 1)
        user_id = session['user_id']

        # Fetch ALL lessons for grade, LEFT JOIN to get completed status (NULL if unassigned)
        c.execute("""
            SELECT l.*, lu.completed 
            FROM lessons l 
            LEFT JOIN lessons_users lu ON (l.id = lu.lesson_id AND lu.user_id = ?)
            WHERE l.grade = ?
            ORDER BY l.id ASC
        """, (user_id, grade))
        raw_lessons = c.fetchall()
        lessons_list = []
        unassigned_ids = []

        for r in raw_lessons:
            lesson_dict = dict(r)
            if lesson_dict.get('mc_options'):
                lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options'])
            # Treat NULL completed as 0 (incomplete/unassigned)
            lesson_dict['completed'] = lesson_dict['completed'] or 0
            lessons_list.append(lesson_dict)
            if lesson_dict['completed'] == 0:
                unassigned_ids.append(lesson_dict['id'])

        # Auto-assign any unassigned ones (all at once, no limit)
        if unassigned_ids:
            c.executemany("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, completed) VALUES (?, ?, 0)", 
                          [(user_id, lid) for lid in unassigned_ids])
            conn.commit()
            logger.info(f"Auto-assigned {len(unassigned_ids)} lessons for user {user_id} in grade {grade}")

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
        if grade == 1:
            trace_word = 'cat'
            spell_word = 'cat'
            sound = '/kæt/'
            mc_question = 'What is the correct spelling?'
            mc_options = ['cat', 'kat', 'ct', 'caat']
            mc_answer = 'cat'
            sentence_answer = 'mat'  # Fixed: Set to 'mat' to match template
            content = f"Learn the short A sound with words like cat and hat."
        else:  # grade 2
            trace_word = 'blue'
            spell_word = 'blue'
            sound = '/bluː/'
            mc_question = 'What is the correct spelling?'
            mc_options = ['blue', 'blu', 'bule', 'bloo']
            mc_answer = 'blue'
            sentence_answer = 'sky'
            content = f"Learn the BL blend with words like blue and black."
    elif subject == 'math':
        if grade == 1:
            a, b = 5, 3
            content = f"What is {a} + {b}?"
            math_answer = str(a + b)
        else:
            a, b = 10, 2
            content = f"What is {a} - {b}?"
            math_answer = str(a - b)

    try:
        conn = get_db()
        c = conn.cursor()
        mc_options_json = json.dumps(mc_options) if mc_options else None
        c.execute('''INSERT INTO lessons (grade, subject, content, trace_word, sound, spell_word, 
                     mc_question, mc_options, mc_answer, math_answer, sentence_answer) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (grade, subject, content, trace_word, sound, spell_word,
                   mc_question, mc_options_json, mc_answer, math_answer, sentence_answer))
        conn.commit()
        lesson_id = c.lastrowid
        c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id) VALUES (?, ?)", 
                  (session['user_id'], lesson_id))
        conn.commit()
        logger.info(f"Generated lesson {lesson_id} for user {session['user_id']}")
        return jsonify({'success': True, 'lesson_id': lesson_id})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500