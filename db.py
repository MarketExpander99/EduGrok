# db.py
import sqlite3
import os
from flask import g
import logging

logger = logging.getLogger(__name__)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('database.db', detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  email TEXT UNIQUE, 
                  password TEXT, 
                  grade INTEGER, 
                  handle TEXT, 
                  theme TEXT DEFAULT 'astronaut',
                  subscribed INTEGER DEFAULT 0, 
                  language TEXT DEFAULT 'en', 
                  star_coins INTEGER DEFAULT 0, 
                  points INTEGER DEFAULT 0)''')
    # Lessons table with type and correct_answer
    c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, 
                  description TEXT, 
                  content TEXT, 
                  type TEXT, 
                  correct_answer TEXT)''')
    # Posts table
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  content TEXT, 
                  media_url TEXT, 
                  created_at TEXT, 
                  likes INTEGER DEFAULT 0, 
                  reposts INTEGER DEFAULT 0, 
                  views INTEGER DEFAULT 0, 
                  subject TEXT, 
                  original_post_id INTEGER, 
                  grade INTEGER, 
                  handle TEXT, 
                  original_handle TEXT, 
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    # Comments table
    c.execute('''CREATE TABLE IF NOT EXISTS comments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  post_id INTEGER, 
                  user_id INTEGER, 
                  content TEXT, 
                  created_at TEXT, 
                  handle TEXT, 
                  FOREIGN KEY (post_id) REFERENCES posts(id), 
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    # Likes table
    c.execute('''CREATE TABLE IF NOT EXISTS likes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  post_id INTEGER, 
                  user_id INTEGER, 
                  FOREIGN KEY (post_id) REFERENCES posts(id), 
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    # Reposts table
    c.execute('''CREATE TABLE IF NOT EXISTS reposts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  post_id INTEGER, 
                  user_id INTEGER, 
                  FOREIGN KEY (post_id) REFERENCES posts(id), 
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    # User lessons table
    c.execute('''CREATE TABLE IF NOT EXISTS user_lessons 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  lesson_id INTEGER, 
                  completed_at TEXT, 
                  FOREIGN KEY (user_id) REFERENCES users(id), 
                  FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
    conn.commit()
    conn.close()
    seed_lessons()
    from achievements_db import init_achievements_tables
    conn = sqlite3.connect('database.db')
    init_achievements_tables(conn.cursor())
    conn.commit()
    conn.close()

def reset_db():
    if os.path.exists('database.db'):
        os.remove('database.db')
    init_db()
    logger.info("Database reset complete")

def seed_lessons():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM lessons')
    lessons = [
        ('Match numbers', 'Drag to pair (e.g., 2x3 to 6)', 'Match 1', 'match', None),
        ('Untitled', 'No description available.', '', 'untitled', None),
        ('Alphabet ABC', 'Trace the Word', 'abc', 'trace', 'abc'),
        ('Spelling Practice', 'Spell the word for the given sound: /æb si/', '/æb si/', 'spelling', 'abc'),
        ('Multiple Choice Example', 'Choose the correct answer', '{"question": "What is 2+2?", "options": ["3", "4", "5"]}', 'multiple_choice', '4'),
        ('Sentence Completion Example', 'Complete the sentence', 'The cat is on the ___.', 'sentence', 'mat')
    ]
    c.executemany('INSERT INTO lessons (title, description, content, type, correct_answer) VALUES (?, ?, ?, ?, ?)', lessons)
    conn.commit()
    conn.close()

def check_db_schema():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    try:
        # Check lessons table
        c.execute("PRAGMA table_info(lessons)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'type' not in columns:
            c.execute("ALTER TABLE lessons ADD COLUMN type TEXT")
            conn.commit()
            logger.info("Added type column to lessons table")
            print("Added type column to lessons table")
        if 'correct_answer' not in columns:
            c.execute("ALTER TABLE lessons ADD COLUMN correct_answer TEXT")
            conn.commit()
            logger.info("Added correct_answer column to lessons table")
            print("Added correct_answer column to lessons table")
        
        # Check users table for subscribed
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'subscribed' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN subscribed INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added subscribed column to users table")
            print("Added subscribed column to users table")
        
        from achievements_db import check_achievements_schema
        check_achievements_schema(conn)
    except Exception as e:
        logger.error(f"DB schema check failed: {str(e)}")
        raise
    finally:
        conn.close()