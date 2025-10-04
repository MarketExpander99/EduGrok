# db.py (updated: Added last_feed_view column check in check_db_schema)
import sqlite3
import os
from flask import g
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def get_db():
    if 'db' not in g:
        try:
            g.db = sqlite3.connect('database.db', detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    return g.db

def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to close database: {str(e)}")

def init_tables():
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # Users table - UPDATED: Added parent_id, role
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
                      points INTEGER DEFAULT 0,
                      parent_id INTEGER,
                      role TEXT DEFAULT 'kid',
                      FOREIGN KEY (parent_id) REFERENCES users(id))''')
        # Lessons table
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      title TEXT,
                      grade INTEGER, 
                      subject TEXT, 
                      content TEXT, 
                      description TEXT,
                      created_at TEXT,
                      trace_word TEXT,
                      spell_word TEXT,
                      sound TEXT,
                      mc_question TEXT,
                      mc_options TEXT,
                      mc_answer TEXT,
                      sentence_question TEXT,
                      sentence_options TEXT,
                      sentence_answer TEXT,
                      math_question TEXT,
                      math_answer TEXT)''')
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
        # Completed lessons table
        c.execute('''CREATE TABLE IF NOT EXISTS completed_lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      lesson_id INTEGER, 
                      completed_at TEXT, 
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
        # Assigned lessons table
        c.execute('''CREATE TABLE IF NOT EXISTS lessons_users 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      lesson_id INTEGER, 
                      assigned_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
        # Lesson responses table
        c.execute('''CREATE TABLE IF NOT EXISTS lesson_responses 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      lesson_id INTEGER, 
                      user_id INTEGER, 
                      activity_type TEXT, 
                      response TEXT, 
                      is_correct INTEGER, 
                      points INTEGER,
                      responded_at TEXT DEFAULT (datetime('now')),
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        # UPDATED: Added friendships table
        c.execute('''CREATE TABLE IF NOT EXISTS friendships 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      requester_id INTEGER,
                      target_id INTEGER,
                      status TEXT DEFAULT 'requested',  -- requested, approved, rejected
                      requested_at TEXT DEFAULT (datetime('now')),
                      approved_at TEXT,
                      FOREIGN KEY (requester_id) REFERENCES users(id),
                      FOREIGN KEY (target_id) REFERENCES users(id))''')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error initializing tables: {str(e)}")
        raise
    finally:
        conn.close()

def init_db():
    try:
        init_tables()
        conn = sqlite3.connect('database.db')
        from achievements_db import init_achievements_tables
        init_achievements_tables(conn.cursor())
        conn.commit()
        check_db_schema()
        seed_lessons()
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise
    finally:
        conn.close()

def reset_db():
    try:
        if os.path.exists('database.db'):
            os.remove('database.db')
        init_db()
        logger.info("Database reset complete")
    except Exception as e:
        logger.error(f"Database reset failed: {str(e)}")
        raise

def seed_lessons():
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('DELETE FROM lessons')
        now = datetime.now().isoformat()
        lessons = [
            ('Lesson 1: Counting to 10', 1, 'math', 'Basic counting lesson', 'Learn to count from 1 to 10 with fun activities.', now, None, None, None, None, None, None, None, None, None, 'What is 2 + 3?', '5'),
            ('Lesson 2: Alphabet ABC', 1, 'language', 'Alphabet introduction', 'Trace and spell the alphabet.', now, 'abc', 'abc', '/æb si/', 'What is the first letter?', json.dumps(['a', 'b', 'c']), 'a', 'The ___ is the first letter.', json.dumps(['abc', 'def', 'a']), 'a', None, None),
            ('Lesson 3: Colors of the Rainbow', 1, 'science', 'Color recognition', 'Identify basic colors.', now, None, None, None, 'What color is the sky?', json.dumps(['blue', 'red', 'green']), 'blue', None, None, None, None, None),
            ('Lesson 4: Phonics A', 1, 'language', 'Phonics for A', 'Practice the sound and spelling of A.', now, 'a', 'a', '/æ/', None, None, None, None, None, None, None, None),
            ('Lesson 5: Phonics B', 1, 'language', 'Phonics for B', 'Practice the sound and spelling of B.', now, 'b', 'b', '/bi/', None, None, None, None, None, None, None, None),
            ('Lesson 6: Phonics C', 1, 'language', 'Phonics for C', 'Practice the sound and spelling of C.', now, 'c', 'c', '/si/', None, None, None, None, None, None, None, None),
            ('Lesson 49: Sentence Cat on Mat', 1, 'language', 'Simple sentence building', 'Complete sentences with basic words.', now, 'cat', 'cat', '/kæt/', 'What is the correct spelling?', json.dumps(['cat', 'kat', 'ct']), 'cat', 'The cat sat on the ___.', json.dumps(['mat', 'dog', 'moon']), 'mat', None, None),
        ]
        c.executemany('''INSERT INTO lessons 
                         (title, grade, subject, content, description, created_at, trace_word, spell_word, sound, mc_question, mc_options, mc_answer, 
                          sentence_question, sentence_options, sentence_answer, math_question, math_answer) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', lessons)
        conn.commit()
        logger.info("Lessons seeded successfully")
    except sqlite3.Error as e:
        logger.error(f"Error seeding lessons: {str(e)}")
        raise
    finally:
        conn.close()

def check_db_schema():
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # Check lessons table for required columns
        c.execute("PRAGMA table_info(lessons)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        required_columns = ['title', 'grade', 'subject', 'content', 'description', 'created_at', 'trace_word', 'spell_word', 'sound', 
                            'mc_question', 'mc_options', 'mc_answer', 'sentence_question', 'sentence_options', 
                            'sentence_answer', 'math_question', 'math_answer']
        for col in required_columns:
            if col not in columns:
                c.execute(f"ALTER TABLE lessons ADD COLUMN {col} TEXT")
                conn.commit()
                logger.info(f"Added {col} column to lessons table")
        # Check users table for required columns - UPDATED: Add parent_id, role
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        required_user_columns = ['email', 'password', 'grade', 'handle', 'theme', 'subscribed', 'language', 'star_coins', 'points', 'parent_id', 'role']
        for col in required_user_columns:
            if col not in columns:
                default = "NULL" if col == 'parent_id' else "'kid'" if col == 'role' else 0 if col in ['subscribed', 'star_coins', 'points'] else "'en'" if col == 'language' else "'astronaut'" if col == 'theme' else "''"
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {'INTEGER' if col in ['parent_id'] else 'TEXT'} DEFAULT {default}")
                conn.commit()
                logger.info(f"Added {col} column to users table")
        # Check posts table for views column
        c.execute("PRAGMA table_info(posts)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'views' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added views column to posts table")
        # UPDATED: Check friendships table
        c.execute("PRAGMA table_info(friendships)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        required_friend_columns = ['requester_id', 'target_id', 'status', 'requested_at', 'approved_at']
        for col in required_friend_columns:
            if col not in columns:
                default = "datetime('now')" if col == 'requested_at' else "NULL" if col == 'approved_at' else "'requested'" if col == 'status' else "NULL"
                col_type = "TEXT" if col in ['status', 'requested_at', 'approved_at'] else "INTEGER"
                c.execute(f"ALTER TABLE friendships ADD COLUMN {col} {col_type} DEFAULT {default}")
                conn.commit()
                logger.info(f"Added {col} column to friendships table")
        # NEW: Add last_feed_view column to users
        c.execute("PRAGMA table_info(users)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'last_feed_view' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN last_feed_view TEXT")
            conn.commit()
            logger.info("Added last_feed_view column to users table")
        from achievements_db import check_achievements_schema
        check_achievements_schema(conn)
    except sqlite3.Error as e:
        logger.error(f"DB schema check failed: {str(e)}")
        raise
    finally:
        conn.close()