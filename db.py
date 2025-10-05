# db.py (Fixed: Added 'type' and 'lesson_id' columns to posts table in init_tables and check_db_schema. Ensured all lessons tuples are exactly 17 items. Added logging for schema changes.)
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
        # Posts table - FIXED: Added type and lesson_id
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
                      type TEXT DEFAULT 'post',
                      lesson_id INTEGER,
                      FOREIGN KEY (user_id) REFERENCES users(id),
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
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
        # FIXED: Grade 1 Week of Oct 6-10, 2025 (20 lessons: 4/day across Math, Language, Science, Social Studies) - All tuples now exactly 17 items
        lessons = [
            # Monday Oct 6
            ('Week 1 Mon: Counting Apples (Math)', 1, 'math', 'Count fall apples and add small groups.', 'Practice number sense with seasonal fruits.', now, None, None, None, None, None, None, None, None, None, 'How many apples? 3 + 2 = ?', '5'),
            ('Week 1 Mon: Phonics - Short A (Language)', 1, 'language', 'Identify words with short A sound.', 'Build phonics skills for reading readiness.', now, 'apple', 'apple', '/æpəl/', 'Which word has short A?', json.dumps(['apple', 'igloo', 'umbrella']), 'apple', 'I see a red ___.', json.dumps(['apple', 'banana', 'car']), 'apple', None, None),
            ('Week 1 Mon: Fall Leaves Change (Science)', 1, 'science', 'Observe why leaves change in fall.', 'Explore seasons and plant life cycles.', now, None, None, None, 'What color do leaves turn in fall?', json.dumps(['red', 'blue', 'yellow']), 'red', None, None, None, None, None),
            ('Week 1 Mon: My Family Roles (Social Studies)', 1, 'social_studies', 'Learn about family members and their jobs.', 'Understand family structures.', now, 'mom', 'mom', '/mɒm/', 'Who cooks dinner?', json.dumps(['mom', 'teacher', 'doctor']), 'mom', 'My ___ helps at home.', json.dumps(['mom', 'dad', 'friend']), 'mom', None, None),
            
            # Tuesday Oct 7
            ('Week 1 Tue: Shapes in Nature (Math)', 1, 'math', 'Identify circles and squares in leaves.', 'Connect shapes to the environment.', now, None, None, None, None, None, None, None, None, None, 'How many sides on a square?', '4'),
            ('Week 1 Tue: Sight Word - The (Language)', 1, 'language', 'Practice reading "the".', 'Build high-frequency word recognition.', now, 'the', 'the', '/ðə/', 'Spell the word for /ðə/.', json.dumps(['the', 'tha', 'thee']), 'the', '___ cat is happy.', json.dumps(['The', 'A', 'An']), 'The', None, None),
            ('Week 1 Tue: Animals Prepare for Winter (Science)', 1, 'science', 'Discuss how squirrels gather nuts.', 'Learn animal adaptations.', now, 'nut', 'nut', '/nʌt/', 'What do squirrels collect?', json.dumps(['nuts', 'leaves', 'rocks']), 'nuts', None, None, None, None, None),
            ('Week 1 Tue: Community Helpers - Teacher (Social Studies)', 1, 'social_studies', 'Role of teachers in school.', 'Explore jobs in the community.', now, 'teach', 'teach', '/tiːtʃ/', 'Who helps you learn?', json.dumps(['teacher', 'firefighter', 'chef']), 'teacher', 'The ___ reads stories.', json.dumps(['teacher', 'doctor', 'pilot']), 'teacher', None, None),
            
            # Wednesday Oct 8
            ('Week 1 Wed: Addition - 1+1=2 (Math)', 1, 'math', 'Add two groups of one.', 'Basic addition facts.', now, None, None, None, None, None, None, None, None, None, '1 + 1 = ?', '2'),
            ('Week 1 Wed: CVC Word - Cat (Language)', 1, 'language', 'Blend C-V-C sounds for "cat".', 'Phonics blending practice.', now, 'cat', 'cat', '/kæt/', 'Spell /k/ /æ/ /t/.', json.dumps(['cat', 'cot', 'cut']), 'cat', 'The ___ sat on the mat.', json.dumps(['cat', 'dog', 'bat']), 'cat', None, None),
            ('Week 1 Wed: Weather in Fall (Science)', 1, 'science', 'What is cooler weather?', 'Seasonal weather patterns.', now, None, None, None, 'What do we wear in fall?', json.dumps(['coat', 'swimsuit', 'sunglasses']), 'coat', None, None, None, None, None),
            ('Week 1 Wed: My School Rules (Social Studies)', 1, 'social_studies', 'Importance of following rules.', 'School community basics.', now, 'rule', 'rule', '/ruːl/', 'What is a rule?', json.dumps(['rule', 'toy', 'book']), 'rule', 'We follow the ___ at school.', json.dumps(['rule', 'game', 'song']), 'rule', None, None),
            
            # Thursday Oct 9
            ('Week 1 Thu: Counting to 5 (Math)', 1, 'math', 'Count objects up to 5.', 'Number sequencing.', now, None, None, None, None, None, None, None, None, None, 'Count: 1,2,3,?,5', '4'),
            ('Week 1 Thu: Rhyming Words (Language)', 1, 'language', 'Find words that rhyme with "hat".', 'Rhyming awareness.', now, 'hat', 'hat', '/hæt/', 'What rhymes with hat?', json.dumps(['cat', 'house', 'sun']), 'cat', 'The ___ is on my head.', json.dumps(['hat', 'shoe', 'book']), 'hat', None, None),
            ('Week 1 Thu: Plants in Fall (Science)', 1, 'science', 'How do trees lose leaves?', 'Plant life cycles.', now, 'leaf', 'leaf', '/liːf/', 'What falls from trees?', json.dumps(['leaves', 'apples', 'birds']), 'leaves', None, None, None, None, None),
            ('Week 1 Thu: Helping at Home (Social Studies)', 1, 'social_studies', 'Chores and family help.', 'Responsibility in family.', now, 'help', 'help', '/hɛlp/', 'What do you do to help?', json.dumps(['help', 'play', 'sleep']), 'help', 'I ___ mom clean.', json.dumps(['help', 'run', 'eat']), 'help', None, None),
            
            # Friday Oct 10
            ('Week 1 Fri: Subtraction Basics (Math)', 1, 'math', 'Take away one from two.', 'Intro to subtraction.', now, None, None, None, None, None, None, None, None, None, '3 - 1 = ?', '2'),
            ('Week 1 Fri: Simple Sentences (Language)', 1, 'language', 'Build "I see a dog."', 'Sentence structure.', now, 'dog', 'dog', '/dɒɡ/', 'What is a pet?', json.dumps(['dog', 'car', 'tree']), 'dog', 'I see a ___.', json.dumps(['dog', 'house', 'cloud']), 'dog', None, None),
            ('Week 1 Fri: Recycling in Fall (Science)', 1, 'science', 'Why recycle leaves?', 'Environmental care.', now, None, None, None, 'What can we recycle?', json.dumps(['paper', 'food', 'toys']), 'paper', None, None, None, None, None),
            ('Week 1 Fri: Seasons Change (Social Studies)', 1, 'social_studies', 'From summer to fall.', 'Understanding seasons.', now, 'fall', 'fall', '/fɔːl/', 'What season has pumpkins?', json.dumps(['fall', 'winter', 'spring']), 'fall', 'In ___ the leaves change.', json.dumps(['fall', 'summer', 'rain']), 'fall', None, None),
        ]
        # NEW: Verify tuple lengths before insert
        for i, lesson in enumerate(lessons):
            if len(lesson) != 17:
                raise ValueError(f"Lesson {i+1} has {len(lesson)} items, expected 17: {lesson}")
        c.executemany('''INSERT INTO lessons 
                         (title, grade, subject, content, description, created_at, trace_word, spell_word, sound, mc_question, mc_options, mc_answer, 
                          sentence_question, sentence_options, sentence_answer, math_question, math_answer) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', lessons)
        conn.commit()
        logger.info("Grade 1 weekly lessons seeded successfully (20 lessons for Oct 6-10, 2025)")
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
        # Check posts table for views, type, lesson_id columns
        c.execute("PRAGMA table_info(posts)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'views' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added views column to posts table")
        if 'type' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN type TEXT DEFAULT 'post'")
            conn.commit()
            logger.info("Added type column to posts table")
        if 'lesson_id' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN lesson_id INTEGER")
            conn.commit()
            logger.info("Added lesson_id column to posts table")
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