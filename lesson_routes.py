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

        for r in raw_lessons:
            lesson_dict = dict(r)
            if lesson_dict.get('mc_options'):
                lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options'])
            # Keep completed as is (None if unassigned, 0 or 1 if assigned)
            lessons_list.append(lesson_dict)

        # Removed auto-assign

        return render_template('lessons.html.j2', lessons=lessons_list, grade=grade)
    except Exception as e:
        logger.error(f"Fetch lessons failed: {str(e)}")
        flash('Server error', 'error')
        return redirect(url_for('home'))

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    grade = session.get('grade', 1)
    user_id = session['user_id']

    try:
        conn = get_db()
        c = conn.cursor()

        # Example placeholder lesson (can be expanded with more logic or randomization)
        subject = 'math'  # Example; could randomize or based on input
        title = 'Generated Lesson'
        description = 'This is a newly generated lesson for practice.'
        content = 'Learn and complete the activities below!'

        # Insert new lesson into DB
        c.execute('''INSERT INTO lessons (grade, subject, title, description, content) 
                     VALUES (?, ?, ?, ?, ?)''', (grade, subject, title, description, content))
        lesson_id = c.lastrowid
        conn.commit()

        # Auto-assign the new lesson to the user's feed
        c.execute("INSERT INTO lessons_users (user_id, lesson_id, completed, assigned_at) VALUES (?, ?, 0, datetime('now'))", (user_id, lesson_id))
        conn.commit()

        logger.info(f"Generated and assigned new lesson {lesson_id} for user {user_id} in grade {grade}")
        return jsonify({'success': True, 'message': 'New lesson generated and added to your feed!'})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

def add_to_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Login required'}), 401

    data = request.get_json()
    if not data or 'lesson_id' not in data:
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400

    lesson_id = data['lesson_id']
    user_id = session['user_id']

    try:
        conn = get_db()
        c = conn.cursor()

        # Check if already assigned
        c.execute("SELECT completed FROM lessons_users WHERE user_id = ? AND lesson_id = ?", (user_id, lesson_id))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Lesson already added to feed'}), 400

        # Assign to user
        c.execute("INSERT INTO lessons_users (user_id, lesson_id, completed, assigned_at) VALUES (?, ?, 0, datetime('now'))", (user_id, lesson_id))
        conn.commit()

        logger.info(f"Added lesson {lesson_id} to feed for user {user_id}")
        return jsonify({'success': True, 'message': 'Lesson added to your feed!'})
    except Exception as e:
        logger.error(f"Add to feed failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

# FIXED: Completed truncated function - assigns 3 random unassigned lessons for grade
def schedule_lessons():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    grade = session.get('grade', 1)
    user_id = session['user_id']

    try:
        conn = get_db()
        c = conn.cursor()

        # Get available lessons not assigned/completed for grade
        c.execute("""
            SELECT id FROM lessons 
            WHERE grade = ? AND id NOT IN (
                SELECT lesson_id FROM lessons_users WHERE user_id = ?
            )
            ORDER BY RANDOM() LIMIT 3
        """, (grade, user_id))
        lesson_ids = [row[0] for row in c.fetchall()]

        assigned_count = 0
        for lid in lesson_ids:
            c.execute("INSERT INTO lessons_users (user_id, lesson_id, completed, assigned_at) VALUES (?, ?, 0, datetime('now'))", (user_id, lid))
            assigned_count += 1

        conn.commit()
        logger.info(f"Scheduled {assigned_count} lessons for user {user_id} in grade {grade}")
        return jsonify({'success': True, 'message': f'Scheduled {assigned_count} new lessons to your feed!'})
    except Exception as e:
        logger.error(f"Schedule lessons failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500