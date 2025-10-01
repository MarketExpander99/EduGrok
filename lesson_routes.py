# lesson_routes.py
from flask import session, request, jsonify, render_template, redirect, url_for, flash
from db import get_db
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

def check_lesson():
    logger.debug("Check lesson route called with data: %s", request.data)
    if 'user_id' not in session:
        logger.warning("Unauthorized access to check_lesson")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        logger.error("No JSON data in request")
        return jsonify({'success': False, 'error': 'No data'}), 400
    lesson_id = data.get('lesson_id')
    if not lesson_id:
        logger.error("Missing lesson_id in data")
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    complete = data.get('complete_lesson', False)
    activity_type = data.get('activity_type')
    response = data.get('response')
    # Normalize response
    if response is not None:
        response = str(response).strip().lower()
    else:
        response = ''

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson = c.fetchone()
        if not lesson:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404

        if complete:
            c.execute("SELECT * FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
            if c.fetchone():
                return jsonify({'success': True})
            c.execute("INSERT INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)", 
                      (session['user_id'], lesson_id, datetime.now().isoformat()))
            points = 10
            c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, ?, datetime('now'))", 
                      (session['user_id'], points))
            conn.commit()
            logger.info(f"Lesson {lesson_id} completed by user {session['user_id']}, awarded {points} points")
            return jsonify({'success': True, 'points': points})

        if activity_type and response:
            expected = ''
            message_correct = 'Correct!'
            message_wrong = 'Try again!'
            points = 5
            if activity_type == 'math_fill':
                expected = str(lesson['math_answer'] or '').strip().lower()
                message_correct = 'Correct!'
            elif activity_type == 'trace_complete':
                expected = str(lesson['trace_word'] or '').strip().lower()
                message_correct = 'Correct! Great job tracing the word.'
                message_wrong = 'Try again! Make sure to type the word exactly as shown.'
            elif activity_type == 'spelling_complete':
                expected = str(lesson['spell_word'] or '').strip().lower()
                message_correct = 'Correct! You spelled the word correctly.'
                message_wrong = 'Try again! Check the spelling carefully.'
            elif activity_type == 'mc_choice':
                expected = str(lesson['mc_answer'] or '').strip().lower()
                message_correct = 'Correct! You chose the right answer.'
                message_wrong = 'Incorrect. Try again!'
            elif activity_type == 'sentence_complete':
                expected = str(lesson['sentence_answer'] or '').strip().lower()
                message_correct = 'Perfect!'
                message_wrong = 'Try again!'
            elif activity_type == 'match_game':
                expected = 'demo_match'  # Still demo, as no DB field for match answers

            if expected:
                is_correct = response == expected
                if is_correct:
                    c.execute("INSERT INTO user_points (user_id, points, earned_at) VALUES (?, ?, datetime('now'))", 
                              (session['user_id'], points))
                    conn.commit()
                    logger.info(f"Activity {activity_type} correct for lesson {lesson_id}, awarded {points} points to user {session['user_id']}")
                    return jsonify({'success': True, 'is_correct': True, 'points': points, 'message': message_correct})
                else:
                    return jsonify({'success': True, 'is_correct': False, 'message': message_wrong})
            else:
                return jsonify({'success': False, 'error': 'No expected answer defined for this activity'}), 400
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500

# The rest of the functions remain the same as in the original, but with potential improvements if needed
def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO completed_lessons (user_id, lesson_id, completed_at) VALUES (?, ?, ?)", (session['user_id'], lesson_id, datetime.now().isoformat()))
        conn.commit()
        flash('Lesson completed', 'success')
        logger.info(f"Lesson {lesson_id} completed by user {session['user_id']}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM completed_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson reset', 'success')
        logger.info(f"Lesson {lesson_id} reset for user {session['user_id']}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def lessons():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    grade = session['grade']
    user_id = session['user_id']
    
    # FIXED: Auto-assign all unassigned lessons for the user's grade to their feed
    c.execute("""
        INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, completed, assigned_at)
        SELECT ?, l.id, 0, datetime('now')
        FROM lessons l
        WHERE l.grade = ? AND l.id NOT IN (
            SELECT lu.lesson_id FROM lessons_users lu WHERE lu.user_id = ?
        )
    """, (user_id, grade, user_id))
    assigned_count = c.rowcount
    if assigned_count > 0:
        conn.commit()
        logger.info(f"Auto-assigned {assigned_count} lessons to user {user_id}'s feed")
    
    # Fetch lessons with assignment status
    c.execute("""
        SELECT l.*, lu.completed, lu.assigned_at
        FROM lessons l
        LEFT JOIN lessons_users lu ON l.id = lu.lesson_id AND lu.user_id = ?
        WHERE l.grade = ?
        ORDER BY l.id
    """, (user_id, grade))
    lessons_raw = c.fetchall()
    
    lessons_list = []
    completed_ids = set()
    for lesson in lessons_raw:
        lesson_dict = dict(lesson)
        if 'mc_options' in lesson_dict and lesson_dict['mc_options']:
            lesson_dict['mc_options'] = json.loads(lesson_dict['mc_options'])
        if 'sentence_options' in lesson_dict and lesson_dict['sentence_options']:
            lesson_dict['sentence_options'] = json.loads(lesson_dict['sentence_options'])
        # Mark as completed only if assigned and completed
        lesson_dict['completed'] = lesson_dict.get('completed', 0) == 1
        if lesson_dict['completed']:
            completed_ids.add(lesson_dict['id'])
        lessons_list.append(lesson_dict)
    
    logger.info(f"Fetched {len(lessons_list)} lessons for user {session['user_id']}, grade {session['grade']}, {len(completed_ids)} completed")
    return render_template('lessons.html.j2', lessons=lessons_list, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def generate_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    subject = request.form.get('subject')
    if not subject:
        return jsonify({'success': False, 'error': 'Missing subject'}), 400
    try:
        conn = get_db()
        c = conn.cursor()
        content = f"New lesson in {subject} for grade {session['grade']}"
        c.execute("INSERT INTO lessons (grade, subject, content, created_at) VALUES (?, ?, ?, ?)", 
                  (session['grade'], subject, content, datetime.now().isoformat()))
        lesson_id = c.lastrowid
        # FIXED: Auto-assign the generated lesson
        c.execute("INSERT INTO lessons_users (user_id, lesson_id, completed, assigned_at) VALUES (?, ?, 0, datetime('now'))", 
                  (session['user_id'], lesson_id))
        conn.commit()
        logger.info(f"Generated and assigned lesson {lesson_id} for {subject} by user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def schedule_lessons():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        grade = session['grade']
        user_id = session['user_id']
        # FIXED: Actually schedule 3 random unassigned lessons
        c.execute("""
            INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, completed, assigned_at)
            SELECT ?, l.id, 0, datetime('now')
            FROM lessons l
            WHERE l.grade = ? AND l.id NOT IN (
                SELECT lu.lesson_id FROM lessons_users lu WHERE lu.user_id = ?
            )
            ORDER BY RANDOM() LIMIT 3
        """, (user_id, grade, user_id))
        assigned_count = c.rowcount
        conn.commit()
        logger.info(f"Scheduled {assigned_count} lessons for user {session['user_id']}")
        return jsonify({'success': True, 'assigned': assigned_count})
    except Exception as e:
        logger.error(f"Schedule lessons failed: {str(e)}")
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
        # FIXED: Actually add to feed if not already assigned
        c.execute("""
            INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, completed, assigned_at)
            VALUES (?, ?, 0, datetime('now'))
        """, (session['user_id'], lesson_id))
        if c.rowcount > 0:
            conn.commit()
            logger.info(f"Added lesson {lesson_id} to feed for user {session['user_id']}")
            return jsonify({'success': True, 'message': 'Added to your feed!'})
        else:
            return jsonify({'success': False, 'error': 'Already in feed'})
    except Exception as e:
        logger.error(f"Add to feed failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500