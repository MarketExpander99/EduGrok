# lessons_db.py
import logging
import sqlite3
from datetime import datetime
import json

logger = logging.getLogger(__name__)

def init_lessons_tables(c):
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      grade INTEGER, 
                      subject TEXT, 
                      content TEXT, 
                      created_at TEXT,
                      trace_word TEXT,
                      spell_word TEXT,
                      sound TEXT,
                      mc_question TEXT,
                      mc_options TEXT,  -- JSON string
                      mc_answer TEXT,
                      sentence_question TEXT,
                      sentence_options TEXT,  -- JSON string
                      sentence_answer TEXT,
                      math_question TEXT,
                      math_answer TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS completed_lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      lesson_id INTEGER, 
                      completed_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
        # FIXED: Added lessons_users for assignments
        c.execute('''CREATE TABLE IF NOT EXISTS lessons_users 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      lesson_id INTEGER, 
                      completed INTEGER DEFAULT 0,
                      assigned_at TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
        # FIXED: Added lesson_responses for activity tracking
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
    except sqlite3.Error as e:
        logger.error(f"Error initializing lessons tables: {e}")
        raise

def check_lessons_schema(conn):
    c = conn.cursor()
    try:
        # Check and add new columns if missing
        c.execute("PRAGMA table_info(lessons)")
        columns = {col[1] for col in c.fetchall()}
        new_columns = [
            ('created_at', 'TEXT'),  # FIXED: Added created_at to ensure it's migrated if missing
            ('trace_word', 'TEXT'),
            ('spell_word', 'TEXT'),
            ('sound', 'TEXT'),
            ('mc_question', 'TEXT'),
            ('mc_options', 'TEXT'),
            ('mc_answer', 'TEXT'),
            ('sentence_question', 'TEXT'),
            ('sentence_options', 'TEXT'),
            ('sentence_answer', 'TEXT'),
            ('math_question', 'TEXT'),
            ('math_answer', 'TEXT')
        ]
        for col_name, col_type in new_columns:
            if col_name not in columns:
                c.execute(f"ALTER TABLE lessons ADD COLUMN {col_name} {col_type}")
                conn.commit()
                logger.info(f"Added {col_name} column to lessons table")
        
        for table in ['lessons', 'completed_lessons', 'lessons_users', 'lesson_responses']:
            try:
                c.execute(f"PRAGMA table_info({table})")
                if not c.fetchall():
                    logger.error(f"Table {table} missing")
                    raise ValueError(f"Table {table} missing")
            except sqlite3.OperationalError:
                logger.error(f"Table {table} does not exist")
                raise ValueError(f"Table {table} missing")
    except Exception as e:
        logger.error(f"Lessons schema check failed: {str(e)}")
        raise

def seed_lessons(conn):
    now = datetime.now().isoformat()
    lessons = [
        # Example with new fields; set to None or appropriate values
        (1, 'math', 'Lesson 1: Counting to 10', now, None, None, None, None, None, None, None, None, None, 'What is 2 + 3?', '5'),
        (1, 'language', 'Lesson 2: Alphabet ABC', now, 'abc', 'abc', '/æb si/', 'What is the first letter?', json.dumps(['a', 'b', 'c']), 'a', 'The ___ is the first letter.', json.dumps(['abc', 'def', 'a']), 'a', None, None),
        (1, 'science', 'Lesson 3: Colors of the Rainbow', now, None, None, None, 'What color is the sky?', json.dumps(['blue', 'red', 'green']), 'blue', None, None, None, None, None),
        (1, 'language', 'Lesson 4: Phonics A', now, 'a', 'a', '/æ/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 5: Phonics B', now, 'b', 'b', '/bi/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 6: Phonics C', now, 'c', 'c', '/si/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 49: Sentence Cat on Mat', now, 'cat', 'cat', '/kæt/', 'What is the correct spelling?', json.dumps(['cat', 'kat', 'ct']), 'cat', 'The cat sat on the ___.', json.dumps(['mat', 'dog', 'moon']), 'mat', None, None),
        # Add more lessons with appropriate fields as needed
    ]
    c = conn.cursor()
    for values in lessons:
        c.execute("""INSERT INTO lessons 
                     (grade, subject, content, created_at, trace_word, spell_word, sound, mc_question, mc_options, mc_answer, 
                      sentence_question, sentence_options, sentence_answer, math_question, math_answer) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
    conn.commit()
    logger.info("Seeded lessons with updated fields")