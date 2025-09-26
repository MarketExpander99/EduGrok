# assess_routes.py
from flask import session, request, flash, redirect, url_for, render_template
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from db import get_db

def assess():
    logger.debug("Assess route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    questions = [
        {"q": "Math: 2 + 3 = ?", "a": ["5", "6", "4"], "correct": "5"},
        {"q": "Language: Pick a word that rhymes with 'cat'.", "a": ["Hat", "Dog", "Car"], "correct": "Hat"},
        {"q": "Science: What do plants need to grow?", "a": ["Water", "Sand", "Rocks"], "correct": "Water"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"},
        {"q": "Example Q6", "a": ["Example6", "Wrong", "Wrong"], "correct": "Example6"},
        {"q": "Example Q7", "a": ["Example7", "Wrong", "Wrong"], "correct": "Example7"},
        {"q": "Example Q8", "a": ["Example8", "Wrong", "Wrong"], "correct": "Example8"},
        {"q": "Example Q9", "a": ["Example9", "Wrong", "Wrong"], "correct": "Example9"},
        {"q": "Example Q10", "a": ["Example10", "Wrong", "Wrong"], "correct": "Example10"}
    ]
    if request.method == 'POST':
        correct_answers = ["5", "Hat", "Water", "Example4", "Example5", "Example6", "Example7", "Example8", "Example9", "Example10"]
        score = sum(1 for i in range(1, 11) if request.form.get(f'q{i}') == correct_answers[i-1])
        grade = 1 if score < 4 else 2 if score < 7 else 3
        conn = None
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET grade = ? WHERE id = ?", (grade, session['user_id']))
            conn.commit()
            session['grade'] = grade
            flash('Assessment completed', 'success')
            logger.info(f"User {session['user_id']} completed assessment with score {score}, new grade {grade}")
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Assess failed: {str(e)}")
            if conn:
                conn.rollback()
            flash('Server error', 'error')
            return render_template('assess.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        finally:
            if conn:
                conn.close()
    return render_template('assess.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def take_test():
    logger.debug("Test route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    questions = [
        {"q": "Math: 4 + 5 = ?", "a": ["9", "8", "10"], "correct": "9"},
        {"q": "Example Q2", "a": ["Example2", "Wrong", "Wrong"], "correct": "Example2"},
        {"q": "Example Q3", "a": ["Example3", "Wrong", "Wrong"], "correct": "Example3"},
        {"q": "Example Q4", "a": ["Example4", "Wrong", "Wrong"], "correct": "Example4"},
        {"q": "Example Q5", "a": ["Example5", "Wrong", "Wrong"], "correct": "Example5"}
    ]
    if request.method == 'POST':
        correct_answers = ["9", "Example2", "Example3", "Example4", "Example5"]
        score = sum(1 for i in range(1, 6) if request.form.get(f'q{i}') == correct_answers[i-1])
        conn = None
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO tests (user_id, grade, score, date) VALUES (?, ?, ?, ?)", 
                      (session['user_id'], session['grade'], score, datetime.now().isoformat()))
            points_award = score * 2
            c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)", (session['user_id'], session['user_id'], points_award))
            conn.commit()
            flash('Test completed', 'success')
            logger.info(f"User {session['user_id']} completed test with score {score}, awarded {points_award} points")
            return redirect(url_for('game', score=score))
        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
            if conn:
                conn.rollback()
            flash('Server error', 'error')
            return render_template('test.html.j2', error="Server error", questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))
        finally:
            if conn:
                conn.close()
    return render_template('test.html.j2', questions=questions, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'))

def game():
    logger.debug("Game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    score = int(request.args.get('score', 0))
    difficulty = 'easy' if score < 3 else 'hard'
    logger.info(f"User {session['user_id']} accessed game with difficulty {difficulty}")
    return render_template('game.html.j2', difficulty=difficulty, theme=session.get('theme', 'astronaut'), language=session.get('language', 'en'), score=score)