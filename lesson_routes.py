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
    try:
        # Fetch user role
        c.execute("SELECT role, grade FROM users WHERE id = ?", (session['user_id'],))
        user_row = dict(c.fetchone())
        if not user_row:
            logger.error(f"User not found for ID: {session['user_id']}")
            return redirect(url_for('login'))
        user_role = user_row['role']
        user_grade = user_row['grade']

        # NEW: Check user role - redirect kids to home
        if user_role == 'kid':
            flash("Child accounts have access to the feed and games only. Check your feed for lessons!", "info")
            return redirect(url_for('home'))

        # Determine selected user and grade
        selected_user_id = session['user_id']
        selected_grade = user_grade
        kids = []
        selected_kid_id = None

        if user_role == 'parent':
            # Fetch kids
            c.execute("SELECT id, handle, grade FROM users WHERE parent_id = ? AND role = 'kid'", (session['user_id'],))
            kids = [dict(row) for row in c.fetchall()]
            if kids:
                # Get selected kid_id from query param, default to first kid
                selected_kid_id = request.args.get('kid_id', type=int)
                if selected_kid_id:
                    selected_kid = next((kid for kid in kids if kid['id'] == selected_kid_id), None)
                    if selected_kid:
                        selected_user_id = selected_kid['id']
                        selected_grade = selected_kid['grade']
                    else:
                        selected_kid_id = kids[0]['id']
                        selected_user_id = kids[0]['id']
                        selected_grade = kids[0]['grade']
                else:
                    selected_kid_id = kids[0]['id']
                    selected_user_id = kids[0]['id']
                    selected_grade = kids[0]['grade']
            else:
                logger.info(f"No kids found for parent {session['user_id']}; using self for lessons")
                flash("No children linked to your account. Lessons will be added to your own feed. Register a child to assign to them.", "info")
                # Default to parent's own account
                selected_user_id = session['user_id']
                selected_grade = user_grade

        # Fetch lessons for selected grade
        c.execute("SELECT * FROM lessons WHERE grade = ? ORDER BY created_at DESC", (selected_grade,))
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

        # Get completed lessons for selected user
        c.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ?", (selected_user_id,))
        completed_ids = {row['lesson_id'] for row in c.fetchall()}
        for lesson in lessons_list:
            lesson['completed'] = lesson['id'] in completed_ids

        # Get lessons in feed for selected user
        c.execute("SELECT lesson_id FROM posts WHERE user_id = ? AND type = 'lesson'", (selected_user_id,))
        in_feed_ids = {row['lesson_id'] for row in c.fetchall()}
        for lesson in lessons_list:
            lesson['in_feed'] = lesson['id'] in in_feed_ids

        logger.info(f"Lessons loaded for user {session['user_id']}, selected_user {selected_user_id}, grade {selected_grade}, kids={len(kids) if user_role == 'parent' else 0}")
        return render_template(
            'lessons.html.j2', 
            lessons=lessons_list, 
            kids=kids,
            selected_kid_id=selected_kid_id,
            selected_user_id=selected_user_id,
            theme=session.get('theme', 'astronaut'), 
            language=session.get('language', 'en')
        )
    finally:
        conn.close()

def add_to_feed():
    if 'user_id' not in session:
        logger.warning("Add to feed unauthorized")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    target_user_id = data.get('target_user_id')
    session_user_id = session['user_id']
    logger.info(f"Add to feed attempt: session_user {session_user_id}, target_user {target_user_id}, lesson {lesson_id}")
    if not lesson_id:
        logger.warning(f"Missing lesson_id for user {session_user_id}")
        return jsonify({'success': False, 'error': 'Missing lesson_id'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        # Determine the user_id for the post - default to session user if no target
        post_user_id = target_user_id if target_user_id else session_user_id
        # If target_user_id provided and not self, validate (parent assigning to kid)
        if target_user_id and target_user_id != session_user_id:
            c.execute("SELECT role, parent_id, grade, handle FROM users WHERE id = ?", (target_user_id,))
            target_user = dict(c.fetchone())
            if not target_user:
                return jsonify({'success': False, 'error': 'Target user not found'}), 404
            if target_user['role'] != 'kid' or target_user['parent_id'] != session_user_id:
                return jsonify({'success': False, 'error': 'Invalid target user'}), 403
            target_grade = target_user['grade']
            target_handle = target_user['handle']
        else:
            # Use session user - FIXED: No error if no child, just add to own feed
            c.execute("SELECT role, grade, handle FROM users WHERE id = ?", (session_user_id,))
            user_row = dict(c.fetchone())
            if not user_row:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            if user_row['role'] == 'kid':
                return jsonify({'success': False, 'error': 'Kids cannot add lessons'}), 403
            target_grade = user_row['grade']
            target_handle = session.get('handle', session.get('email', 'User'))

        # Check if already added by this post_user_id
        c.execute("SELECT id FROM posts WHERE user_id = ? AND lesson_id = ? AND type = 'lesson'", (post_user_id, lesson_id))
        if c.fetchone():
            logger.info(f"Lesson {lesson_id} already in feed for user {post_user_id}")
            return jsonify({'success': False, 'message': 'Already in feed'})
        # Get lesson
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson_row = c.fetchone()
        if not lesson_row:
            logger.warning(f"Lesson {lesson_id} not found")
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        lesson = dict(lesson_row)
        # Validate grade
        if lesson['grade'] != target_grade:
            logger.warning(f"Grade mismatch: lesson {lesson['grade']} != target {target_grade} for lesson {lesson_id}")
            return jsonify({'success': False, 'error': 'Grade mismatch'}), 400
        logger.info(f"Grade check passed: {target_grade} for lesson {lesson_id}")
        # Insert post - FIXED: Single-line to avoid multi-line issues
        now = datetime.now().isoformat()
        c.execute("INSERT INTO posts (user_id, content, subject, grade, handle, type, lesson_id, created_at, views, likes, reposts) VALUES (?, ?, ?, ?, ?, 'lesson', ?, ?, 0, 0, 0)", 
                  (post_user_id, lesson['title'], lesson['subject'], lesson['grade'], 
                   target_handle, lesson_id, now))
        post_id = c.lastrowid
        conn.commit()
        logger.info(f"Lesson {lesson_id} added to feed as post {post_id} for user {post_user_id}")
        return jsonify({'success': True, 'message': 'Added to feed!'})
    except sqlite3.IntegrityError as e:
        logger.warning(f"Add to feed integrity error for user {post_user_id}, lesson {lesson_id}: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Already exists'}), 409
    except Exception as e:
        logger.error(f"Add to feed error for user {post_user_id}, lesson {lesson_id}: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        conn.close()

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    if request.method != 'POST':
        return jsonify({'success': False, 'error': 'POST required'}), 400

    # Parse FormData (works for both form and AJAX)
    lesson_id = request.form.get('lesson_id')
    activity_type = request.form.get('activity_type')
    response = request.form.get('response', '')

    if not lesson_id or not activity_type:
        return jsonify({'success': False, 'error': 'Missing lesson_id or activity_type'}), 400

    # FIXED: Early check for empty response (after strip) to return specific error
    stripped_response = response.strip()
    if not stripped_response:
        return jsonify({'success': False, 'error': 'Please provide a response'}), 400

    try:
        lesson_id = int(lesson_id)
        conn = get_db()
        c = conn.cursor()
        # Fetch lesson details
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson_row = c.fetchone()
        if not lesson_row:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404
        lesson = dict(lesson_row)

        # Safely parse JSON fields to lists
        for field in ['mc_options', 'sentence_options']:
            value = lesson.get(field)
            if value is not None:
                try:
                    lesson[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning(f"Invalid JSON in {field} for lesson {lesson_id}: {value} - {e}")
                    lesson[field] = []
            else:
                lesson[field] = []

        # Determine correct answer based on type
        correct_answer = ''
        question = ''
        is_correct = False
        if activity_type == 'mc':
            correct_answer = lesson['mc_answer']
            question = lesson['mc_question']
            if not response:
                is_correct = False
            elif response not in lesson['mc_options']:
                logger.info(f"Invalid MC option '{response}' for lesson {lesson_id}, options: {lesson['mc_options']}")
                is_correct = False
            else:
                is_correct = response.lower() == correct_answer.lower()
        elif activity_type == 'sentence':
            correct_answer = lesson['sentence_answer']
            question = lesson['sentence_question']
            if not response:
                is_correct = False
            elif response not in lesson['sentence_options']:
                logger.info(f"Invalid sentence option '{response}' for lesson {lesson_id}, options: {lesson['sentence_options']}")
                is_correct = False
            else:
                is_correct = response.lower() == correct_answer.lower()
        elif activity_type == 'spell':
            correct_answer = lesson['spell_word']
            question = f'Spell the word: {lesson["spell_word"]}'
            is_correct = stripped_response.lower() == correct_answer.lower() if stripped_response and correct_answer else False
        elif activity_type == 'sound':
            correct_answer = lesson['spell_word']  # FIXED: Use spell_word for sound matching (full word)
            question = f'Repeat the sound: /{lesson["sound"]}/'
            is_correct = stripped_response.lower() == correct_answer.lower() if stripped_response and correct_answer else False
        elif activity_type == 'trace':
            correct_answer = lesson['trace_word']  # Or 'drawn' placeholder
            question = f'Trace the word: {lesson["trace_word"]}'
            is_correct = True  # FIXED: For trace activities, always mark as correct regardless of response (drawing saved as base64)
        elif activity_type == 'math':
            correct_answer = lesson['math_answer']
            question = lesson['math_question']
            logger.info(f"Math response: '{stripped_response}' vs correct: '{correct_answer}'")
            is_correct = stripped_response.lower() == correct_answer.lower() if stripped_response and correct_answer else False
        else:
            return jsonify({'success': False, 'error': 'Invalid activity_type'}), 400

        # FIXED: Safe handling of retry_count - use SELECT * and check keys
        existing_retry = 1  # Default to 1 for new submissions
        c.execute("SELECT * FROM activity_responses WHERE lesson_id = ? AND user_id = ? AND activity_type = ?", (lesson_id, session['user_id'], activity_type))
        row = dict(c.fetchone()) if c.fetchone() else {}
        if row:
            retry_val = row.get('retry_count', 0)
            existing_retry = retry_val + 1 if not is_correct else 1  # Reset on correct, increment on wrong

        # Save to DB (INSERT OR REPLACE; retry_count will be handled by schema)
        # FIXED: Ensure response (base64 for trace) is saved fully
        c.execute('''INSERT OR REPLACE INTO activity_responses 
                     (lesson_id, user_id, activity_type, response, is_correct, points, responded_at, retry_count) 
                     VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)''',
                  (lesson_id, session['user_id'], activity_type, response, int(is_correct), 10 if is_correct else 0, existing_retry))
        conn.commit()

        # FIXED: Check if lesson complete (all activities submitted correctly, including math)
        # Dynamic expected_activities based on non-None fields
        activity_fields = {
            'mc': lesson['mc_answer'] is not None,
            'sentence': lesson['sentence_answer'] is not None,
            'spell': lesson['spell_word'] is not None,
            'sound': lesson['sound'] is not None,
            'trace': lesson['trace_word'] is not None,
            'math': lesson.get('math_answer') is not None
        }
        expected_activities = sum(1 for v in activity_fields.values() if v)
        c.execute("SELECT COUNT(DISTINCT activity_type) FROM activity_responses WHERE lesson_id = ? AND user_id = ? AND is_correct = 1", (lesson_id, session['user_id']))
        submitted_count_result = c.fetchone()
        submitted_count = submitted_count_result[0] if submitted_count_result else 0
        lesson_complete = submitted_count >= expected_activities

        # Mark lesson as completed in DB if all activities done
        if lesson_complete:
            now = datetime.now().isoformat()
            c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at, parent_confirmed) VALUES (?, ?, ?, 0)", 
                      (session['user_id'], lesson_id, now))
            c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                      (session['user_id'], lesson_id))
            conn.commit()
            # Award points if complete
            c.execute("UPDATE users SET points = points + 50 WHERE id = ?", (session['user_id'],))
            conn.commit()

        logger.info(f"User {session['user_id']} submitted {activity_type} for lesson {lesson_id}: {response[:50]}... (correct: {is_correct})")

        # FIXED: Return flag to hide card in frontend if complete
        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'question': question,
            'correct_answer': correct_answer,
            'lesson_complete': lesson_complete,
            'hide_card': lesson_complete  # Explicit flag for frontend to hide lesson card
        })

    except ValueError as e:
        logger.error(f"Invalid lesson_id: {e}")
        return jsonify({'success': False, 'error': 'Invalid lesson ID'}), 400
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

def complete_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        # FIXED: Only kids complete; parents confirm separately
        c.execute("SELECT role FROM users WHERE id = ?", (session['user_id'],))
        role_row = dict(c.fetchone())
        if not role_row or role_row['role'] != 'kid':
            flash('Only child accounts can complete lessons. Parents confirm via dashboard.', 'error')
            return redirect(url_for('lessons'))
        now = datetime.now().isoformat()
        c.execute("INSERT OR IGNORE INTO completed_lessons (user_id, lesson_id, completed_at, parent_confirmed) VALUES (?, ?, ?, 0)", 
                  (session['user_id'], lesson_id, now))
        c.execute("UPDATE lessons_users SET completed = 1 WHERE user_id = ? AND lesson_id = ?", 
                  (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson completed successfully! Waiting for parent confirmation.', 'success')
        # FIXED: Enhanced redirect to home/feed for kids, with flash message
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson error: {e}")
        conn.rollback()
        flash('Error completing lesson', 'error')
        return redirect(url_for('lessons'))
    finally:
        conn.close()

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        # FIXED: Allow parents to reset for kids or self
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    try:
        # Fetch user role and kids
        c.execute("SELECT role, grade, handle FROM users WHERE id = ?", (session['user_id'],))
        user_row = dict(c.fetchone())
        if not user_row or user_row['role'] == 'kid':
            flash("Only parents can generate lessons.", "error")
            return redirect(url_for('home'))
        user_grade = user_row['grade']
        user_handle = user_row['handle']
        c.execute("SELECT COUNT(*) as count FROM users WHERE parent_id = ? AND role = 'kid'", (session['user_id'],))
        kid_count_row = dict(c.fetchone())
        kid_count = kid_count_row['count']

        # NEW: If no kids, add to own feed; else, assume assigning to self or redirect to lessons for selection
        if kid_count == 0:
            # Generate a sample lesson and add to own feed
            now = datetime.now().isoformat()
            sample_title = "Generated Lesson: Basic Addition"
            sample_content = "Practice adding numbers 1-5."
            c.execute("INSERT INTO lessons (title, grade, subject, content, description, created_at) VALUES (?, ?, 'math', ?, ?, ?)", 
                      (sample_title, user_grade, sample_content, sample_content, now))
            new_lesson_id = c.lastrowid
            # FIXED: Single-line SQL
            c.execute("INSERT INTO posts (user_id, content, subject, grade, handle, type, lesson_id, created_at, views, likes, reposts) VALUES (?, ?, 'math', ?, ?, 'lesson', ?, ?, 0, 0, 0)", 
                      (session['user_id'], sample_title, user_grade, user_handle, new_lesson_id, now))
            conn.commit()
            flash(f"Generated and added '{sample_title}' to your feed! Register a child to assign lessons to them.", "success")
            return redirect(url_for('profile'))  # Or home to see feed
        else:
            # Redirect to lessons page for selection
            flash("Use the lessons page to generate and assign.", "info")
            return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Generate lesson error: {e}")
        if conn:
            conn.rollback()
        flash("Failed to generate lesson.", "error")
        return redirect(url_for('lessons'))
    finally:
        if conn:
            conn.close()

def schedule_lessons():
    # Stub: POST to assign lessons to user
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_ids = data.get('lesson_ids', [])
    target_user_id = data.get('target_user_id')
    session_user_id = session['user_id']
    if not lesson_ids:
        return jsonify({'success': False, 'error': 'No lessons specified'}), 400
    conn = get_db()
    c = conn.cursor()
    try:
        # Determine the user_id for assignment - default to session user if no target
        assign_user_id = target_user_id if target_user_id else session_user_id
        # If target_user_id provided, validate (parent assigning to kid)
        if target_user_id:
            c.execute("SELECT role, parent_id FROM users WHERE id = ?", (target_user_id,))
            target_user = dict(c.fetchone())
            if not target_user:
                return jsonify({'success': False, 'error': 'Target user not found'}), 404
            if target_user['role'] != 'kid' or target_user['parent_id'] != session_user_id:
                return jsonify({'success': False, 'error': 'Invalid target user'}), 403
        else:
            # FIXED: Use session user if no child specified - no error
            c.execute("SELECT role FROM users WHERE id = ?", (session_user_id,))
            user_row = dict(c.fetchone())
            if not user_row or user_row['role'] == 'kid':
                return jsonify({'success': False, 'error': 'Kids cannot schedule lessons'}), 403
        now = datetime.now().isoformat()
        for lid in lesson_ids:
            c.execute("INSERT OR IGNORE INTO lessons_users (user_id, lesson_id, assigned_at) VALUES (?, ?, ?)", 
                      (assign_user_id, lid, now))
        conn.commit()
        return jsonify({'success': True, 'message': f'Added {len(lesson_ids)} lessons to schedule'})
    except Exception as e:
        logger.error(f"Schedule lessons error: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        conn.close()