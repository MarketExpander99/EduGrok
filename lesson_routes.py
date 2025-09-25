from flask import session, request, jsonify, flash, redirect, url_for, render_template
import logging
import json

logger = logging.getLogger(__name__)

from db import get_db, seed_lessons

def check_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    activity_type = data.get('activity_type')
    response = data.get('response')
    
    try:
        conn = get_db()
        c = conn.cursor()
        # Get lesson details
        c.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        lesson = dict(c.fetchone())
        
        is_correct = 0
        points_award = 0
        if activity_type == 'math_fill':
            expected = eval(lesson.get('mc_answer', '0'))  # e.g., '6*3' -> 18
            is_correct = 1 if int(response) == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'spelling_complete':
            expected = lesson.get('mc_answer', '').lower()
            is_correct = 1 if response.lower().strip() == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'mc_choice':
            expected = lesson.get('mc_answer', '')
            is_correct = 1 if response == expected else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'sentence_complete':
            expected = lesson.get('mc_answer', '')
            is_correct = 1 if response.lower() in expected.lower() else 0
            points_award = 10 if is_correct else 5
        elif activity_type == 'match_three':
            expected_matches = 3
            user_matches = len([m for m in json.loads(response) if m in json.loads(lesson.get('mc_options', '[]'))])
            is_correct = 1 if user_matches >= expected_matches else 0
            points_award = 10 if is_correct else 5
        
        # Store response
        c.execute("""
            INSERT INTO lesson_responses (lesson_id, user_id, activity_type, response, is_correct, submitted_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (lesson_id, session['user_id'], activity_type, response, is_correct))
        
        # Mark lesson completed and award points if flagged
        if data.get('complete_lesson', False):
            c.execute("UPDATE lessons SET completed = 1 WHERE id = ?", (lesson_id,))
            c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", 
                      (session['user_id'], session['user_id'], points_award))
            c.execute("UPDATE users SET star_coins = star_coins + ? WHERE id = ?", (points_award, session['user_id']))
        
        conn.commit()
        return jsonify({'success': True, 'is_correct': bool(is_correct), 'points': points_award})
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def complete_lesson(lesson_id):
    logger.debug(f"Completing lesson {lesson_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + 5)", (session['user_id'], session['user_id']))
        c.execute("SELECT COUNT(*) FROM badges WHERE user_id = ? AND badge_name = 'Lesson Master'", (session['user_id'],))
        if c.fetchone()[0] == 0:
            c.execute("SELECT COUNT(*) FROM lessons WHERE user_id = ? AND completed = 1", (session['user_id'],))
            if c.fetchone()[0] >= 5:
                c.execute("INSERT INTO badges (user_id, badge_name, awarded_date) VALUES (?, 'Lesson Master', ?)", (session['user_id'], datetime.now().isoformat()))
        conn.commit()
        flash('Lesson completed', 'success')
        logger.info(f"User {session['user_id']} completed lesson {lesson_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def reset_lesson(lesson_id):
    logger.debug(f"Resetting lesson {lesson_id}")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 0 WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (lesson_id, session['user_id']))
        conn.commit()
        flash('Lesson reset for retry', 'success')
        logger.info(f"User {session['user_id']} reset lesson {lesson_id}")
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))

def lessons():
    logger.debug("Lessons route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 ORDER BY id", (session['user_id'], session['grade']))
        lessons_data = c.fetchall()
        lessons_list = [dict(row) for row in lessons_data]
        if not lessons_list:
            logger.warning(f"No lessons found for user {session['user_id']} and grade {session['grade']}")
            seed_lessons()
            c.execute("SELECT id, subject, content, completed FROM lessons WHERE (user_id IS NULL OR user_id = ?) AND grade = ? AND completed = 0 ORDER BY id", (session['user_id'], session['grade']))
            lessons_list = [dict(row) for row in c.fetchall()]
        logger.info(f"Retrieved {len(lessons_list)} lessons for user {session['user_id']}")
        return render_template('lessons.html.j2', lessons=lessons_list, grade=session['grade'], theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Lessons route failed: {str(e)}")
        return render_template('error.html.j2', error=f"Failed to load lessons: {str(e)}", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

def generate_lesson():
    logger.debug("Generate lesson route")
    if 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    grade = request.form.get('grade')
    subject = request.form.get('subject')
    if not grade or not subject or not grade.isdigit() or int(grade) not in [1, 2, 3]:
        logger.error("Invalid grade or subject")
        flash('Invalid grade (1-3) or subject', 'error')
        return redirect(url_for('lessons'))
    try:
        lesson_content = f"Generated {subject} lesson for Grade {grade}"
        trace_word = None
        sound = None
        spell_word = None
        mc_question = None
        mc_options = None
        mc_answer = None
        if subject == 'language':
            word_lists = {
                1: {'word': 'cat', 'sound': '/kæt/'},
                2: {'word': 'ship', 'sound': '/ʃɪp/'},
                3: {'word': 'house', 'sound': '/haʊs/'}
            }
            trace_word = word_lists[int(grade)]['word']
            sound = word_lists[int(grade)]['sound']
            spell_word = trace_word
            mc_question = 'What is the correct spelling?'
            mc_options = f'["{trace_word}", "{trace_word[0]}a{trace_word[1:]}", "{trace_word[:2]}", "{trace_word}a"]'
            mc_answer = trace_word
        elif subject == 'math':
            if int(grade) == 1:
                lesson_content = 'What is 6 + 3? <input type="number" id="math-input" placeholder="Enter answer"> <button onclick="checkMath()">Check</button>'
                mc_answer = '9'
            elif int(grade) == 2:
                lesson_content = 'Match: 2x3=6, 4x2=8, 5x1=5 <div id="match-game"><!-- JS drag-drop --></div>'
                mc_options = '["6", "8", "5"]'
                mc_answer = '6'
            elif int(grade) == 3:
                lesson_content = '6 x 3 = ? <input type="number" id="math-input" placeholder="Enter answer"> <button onclick="checkMath()">Check</button>'
                mc_answer = '18'
        if session.get('language') == 'bilingual':
            lesson_content += f"<br>Afrikaans: Gegenereerde {subject} les vir Graad {grade}"
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO lessons (user_id, grade, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session['user_id'], grade, subject, lesson_content, 0, trace_word, sound, spell_word, mc_question, mc_options, mc_answer))
        conn.commit()
        logger.info(f"Generated lesson for user {session['user_id']}: {subject}")
        flash('Lesson generated', 'success')
        return redirect(url_for('lessons'))
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        conn.rollback()
        flash('Server error', 'error')
        return redirect(url_for('lessons'))