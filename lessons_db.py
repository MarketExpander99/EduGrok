import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

def init_lessons_tables(c):
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER NOT NULL,
            subject TEXT NOT NULL,
            title TEXT,
            description TEXT,
            content TEXT,
            trace_word TEXT,
            spell_word TEXT,
            mc_question TEXT,
            mc_options TEXT,  -- JSON array
            mc_answer TEXT,
            sentence_answer TEXT,
            math_answer TEXT,
            sound TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS lessons_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            assigned_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (lesson_id) REFERENCES lessons(id),
            UNIQUE(user_id, lesson_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS lesson_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            user_id INTEGER,
            activity_type TEXT,
            response TEXT,
            is_correct INTEGER,
            points INTEGER DEFAULT 0,
            responded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (lesson_id) REFERENCES lessons(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        logger.info("Lessons tables initialized")
    except sqlite3.Error as e:
        logger.error(f"Error creating lessons tables: {e}")
        raise

def seed_lessons(conn):
    c = conn.cursor()
    try:
        lessons_data = [
            # Grade 1 samples
            (1, 'math', 'Add Numbers', 'Learn to add simple numbers', 'What is 1 + 1?', None, None, None, None, None, '2', None, None),
            (1, 'language', 'Trace Cat', 'Practice tracing the word "cat"', 'Type the traced word.', 'cat', None, None, None, None, None, None, None),
            (1, 'language', 'Spell Dog', 'Spell the word for /dɒɡ/', 'Type the spelling.', None, 'dog', None, None, None, None, None, '/dɒɡ/'),
            (1, 'science', 'Plants Need Water', 'What do plants need?', 'Multiple choice.', None, None, 'What do plants need to grow?', json.dumps(['Water', 'Sand', 'Rocks']), 'Water', None, None, None),
            (1, 'language', 'Sentence: Cat on Mat', 'Complete the sentence.', 'The cat sat on the ___.', None, None, None, None, None, 'mat', None, None),
            # Grade 2 samples
            (2, 'math', 'Subtract Apples', '2 - 1 = ?', 'Simple subtraction.', None, None, None, None, None, '1', None, None),
            (2, 'language', 'Trace Ship', 'Trace "ship"', 'Type the word.', 'ship', None, None, None, None, None, None, None),
            (2, 'science', 'Animals Move', 'How do animals move?', 'Choice.', None, None, 'How do birds move?', json.dumps(['Fly', 'Swim', 'Crawl']), 'Fly', None, None, None),
            # Grade 3 samples
            (3, 'math', 'Multiply Basics', '2 x 3 = ?', 'Introduction to multiply.', None, None, None, None, None, '6', None, None),
            (3, 'language', 'Spell House', 'Spell /haʊs/', 'Type spelling.', None, 'house', None, None, None, None, None, '/haʊs/')
        ]
        for data in lessons_data:
            c.execute('''INSERT OR IGNORE INTO lessons 
                         (grade, subject, title, description, content, trace_word, spell_word, mc_question, mc_options, mc_answer, math_answer, sentence_answer, sound)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
        conn.commit()
        logger.info("Seeded sample lessons")
        print("Seeded sample lessons")
    except Exception as e:
        logger.error(f"Seed lessons failed: {e}")
        conn.rollback()
        raise

def check_lessons_schema(conn):
    c = conn.cursor()
    try:
        for table in ['lessons', 'lessons_users', 'lesson_responses']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                raise ValueError(f"Table {table} missing")
        # Migrations: e.g., add columns if missing
        c.execute("PRAGMA table_info(lessons)")
        columns = [col[1] for col in c.fetchall()]
        if 'mc_options' not in columns:
            c.execute("ALTER TABLE lessons ADD COLUMN mc_options TEXT")
            conn.commit()
            logger.info("Added mc_options to lessons")
        logger.debug("Lessons schema check passed")
    except Exception as e:
        logger.error(f"Lessons schema check failed: {str(e)}")
        raise