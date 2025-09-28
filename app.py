# lesson_routes.py (complete file - replace your existing one with this)
import logging
import random
import json
from datetime import datetime
from flask import request, jsonify, render_template, redirect, url_for, session, flash
from db import get_db

logger = logging.getLogger(__name__)

def lessons():
    logger.debug("Lessons route accessed")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        user_id = session['user_id']
        grade = session['grade']
        c.execute("""
            SELECT l.* FROM lessons l 
            WHERE l.grade = ? AND (l.user_id IS NULL OR l.user_id = ?) 
            AND l.id NOT IN (SELECT lesson_id FROM lessons_user WHERE user_id = ?)
        """, (grade, user_id, user_id))
        available_lessons = [dict(row) for row in c.fetchall()]
        return render_template('lessons.html.j2', 
                              available_lessons=available_lessons,
                              grade=grade,
                              theme=session.get('theme', 'astronaut'),
                              language=session.get('language', 'en'))
    except Exception as e:
        logger.error(f"Lessons route failed: {str(e)}")
        flash('Failed to load lessons.', 'error')
        return render_template('error.html.j2', error="Failed to load lessons.", theme=session.get('theme', 'astronaut'), language=session.get('language', 'en')), 500

def generate_lesson():
    logger.debug("Generate lesson route")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    # Safeguard: Ensure grade is set
    if 'grade' not in session:
        logger.error("No grade in session")
        return jsonify({'success': False, 'error': 'Grade not set. Please update profile.'}), 400
    
    try:
        grade = session['grade']
        # Simple predefined questions for grade 1 (expand as needed)
        questions = {
            1: [
                ("What is 1 + 1?", "2", "Basic Addition", "Start counting with fingers!"),
                ("How many wheels on a bike?", "2", "Counting Wheels", "Bikes have two wheels."),
                ("2 + 3 = ?", "5", "Farm Addition", "2 cows + 3 sheep."),
                ("4 - 1 = ?", "3", "Subtraction Fun", "4 apples, eat 1."),
                ("What color is the sky?", "blue", "Colors", "Look up!"),
            ]
        }
        if grade not in questions or not questions[grade]:
            return jsonify({'success': False, 'error': 'No questions available for your grade'}), 400
        
        q_data = random.choice(questions[grade])
        question, answer, title, desc = q_data
        
        conn = get_db()
        if conn is None:
            raise Exception("Database connection failed")
        c = conn.cursor()
        c.execute("""
            INSERT INTO lessons (grade, title, description, question, correct_answer, user_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (grade, title, desc, question, answer, session['user_id']))
        conn.commit()
        logger.info(f"Generated lesson for user {session['user_id']}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Generate lesson failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def schedule_lessons():
    logger.debug("Schedule lessons route")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        count = data.get('count', 3)
        if count > 3 or count < 1:
            return jsonify({'success': False, 'error': 'Invalid count'}), 400
        
        conn = get_db()
        c = conn.cursor()
        grade = session['grade']
        user_id = session['user_id']
        c.execute("""
            SELECT id FROM lessons 
            WHERE grade = ? AND (user_id IS NULL OR user_id = ?) 
            AND id NOT IN (SELECT lesson_id FROM lessons_user WHERE user_id = ?)
            ORDER BY RANDOM() LIMIT ?
        """, (grade, user_id, user_id, count))
        available_ids = [row[0] for row in c.fetchall()]
        
        for lid in available_ids:
            c.execute("INSERT OR IGNORE INTO lessons_user (user_id, lesson_id) VALUES (?, ?)", (user_id, lid))
        
        conn.commit()
        logger.info(f"Scheduled {len(available_ids)} lessons for user {user_id}")
        return jsonify({'success': True, 'added': len(available_ids)})
    except Exception as e:
        logger.error(f"Schedule lessons failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

def check_lesson():
    logger.debug("Check lesson route")
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    try:
        lesson_id = request.form.get('lesson_id')
        user_answer = request.form.get('answer', '').strip()
        if not lesson_id or not user_answer:
            flash('Missing lesson or answer.', 'error')
            return redirect(url_for('home'))
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT correct_answer FROM lessons WHERE id = ?", (lesson_id,))
        result = c.fetchone()
        if not result:
            flash('Lesson not found.', 'error')
            return redirect(url_for('home'))
        
        correct_answer = result[0].lower()
        score = 1 if user_answer.lower() == correct_answer else 0
        
        c.execute("""
            INSERT OR REPLACE INTO user_lessons (user_id, lesson_id, user_answer, score) 
            VALUES (?, ?, ?, ?)
        """, (session['user_id'], lesson_id, user_answer, score))
        conn.commit()
        
        if score == 1:
            flash('Correct! Great job! 🎉', 'success')
        else:
            flash(f'Not quite. The answer was "{result[0]}". Keep trying! 💪', 'error')
        
        logger.info(f"User {session['user_id']} answered lesson {lesson_id} with score {score}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Check lesson failed: {str(e)}")
        flash('Failed to submit answer.', 'error')
        return redirect(url_for('home'))

def complete_lesson(lesson_id):
    logger.debug(f"Complete lesson route for {lesson_id}")
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE lessons SET completed = 1 WHERE id = ? AND user_id = ?", (lesson_id, session['user_id']))
        conn.commit()
        flash('Lesson marked as complete!', 'success')
        logger.info(f"User {session['user_id']} completed lesson {lesson_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Complete lesson failed: {str(e)}")
        flash('Failed to complete lesson.', 'error')
        return redirect(url_for('home'))

def reset_lesson(lesson_id):
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM user_lessons WHERE user_id = ? AND lesson_id = ?", (session['user_id'], lesson_id))
        conn.commit()
        flash('Lesson reset! You can try again.', 'success')
        logger.info(f"User {session['user_id']} reset lesson {lesson_id}")
        return redirect(url_for('home'))
    except Exception as e:
        logger.error(f"Reset lesson failed: {str(e)}")
        flash('Failed to reset lesson.', 'error')
        return redirect(url_for('home'))