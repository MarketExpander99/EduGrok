# lesson_routes.py
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
        user_row = c.fetchone()
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
            target_user = c.fetchone()
            if not target_user:
                return jsonify({'success': False, 'error': 'Target user not found'}), 404
            if target_user['role'] != 'kid' or target_user['parent_id'] != session_user_id:
                return jsonify({'success': False, 'error': 'Invalid target user'}), 403
            target_grade = target_user['grade']
            target_handle = target_user['handle']
        else:
            # Use session user - FIXED: No error if no child, just add to own feed
            c.execute("SELECT role, grade, handle FROM users WHERE id = ?", (session_user_id,))
            user_row = c.fetchone()
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
        # Insert post
        now = datetime.now().isoformat()
        c.execute("""INSERT INTO posts 
                     (user_id