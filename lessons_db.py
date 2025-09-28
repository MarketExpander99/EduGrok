# lessons_db.py

import logging
import sqlite3
import json

logger = logging.getLogger(__name__)

def add_column_if_missing(c, table, column, col_type='TEXT'):
    """Safely add a column if it doesn't exist using PRAGMA."""
    c.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in c.fetchall()]
    if column not in columns:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"Added column {column} to {table}")
    else:
        logger.debug(f"Column {column} already exists in {table}")

def init_lessons_tables(c):
    try:
        # Drop and recreate to ensure clean schema without user_id and completed in lessons
        c.execute('DROP TABLE IF EXISTS lesson_responses')
        c.execute('DROP TABLE IF EXISTS tests')
        c.execute('DROP TABLE IF EXISTS lessons')
        c.execute('DROP TABLE IF EXISTS lessons_users')

        # Create lessons table (global, no user_id or completed) - added title and description
        c.execute('''CREATE TABLE lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      title TEXT, 
                      description TEXT, 
                      grade INTEGER, 
                      subject TEXT, content TEXT, 
                      trace_word TEXT, sound TEXT, spell_word TEXT, mc_question TEXT, 
                      mc_options TEXT, mc_answer TEXT, math_answer TEXT, sentence_answer TEXT)''')
        
        # Create lessons_users junction table
        c.execute('''CREATE TABLE lessons_users 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL, 
                      completed BOOLEAN DEFAULT 0, 
                      assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users(id), 
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                      UNIQUE(user_id, lesson_id))''')
        
        c.execute('''CREATE TABLE tests 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, score INTEGER, date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE lesson_responses 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id INTEGER, user_id INTEGER, activity_type TEXT, response TEXT, is_correct BOOLEAN, points INTEGER,
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id), FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_grade_subject ON lessons(grade, subject)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_users_user ON lessons_users(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_users_lesson ON lessons_users(lesson_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tests_user_date ON tests(user_id, date)')
    except sqlite3.Error as e:
        logger.error(f"Error initializing lessons tables: {e}")
        raise

def seed_lessons(conn=None):
    if conn is None:
        from db import get_db
        conn = get_db()
    c = conn.cursor()
    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lessons_unique ON lessons(grade, subject, content)')
        lessons = [
            # Original seeds (kept for variety) - added title and description to each tuple
            (1, 'M Sound Phonics', 'Learn the M sound with words like moon and mars.', 'language', '<p>Learn the M sound with words like <strong>moon</strong> and <strong>mars</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Moon"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 'moon', '/muːn/', 'moon', 'What is the correct spelling?', json.dumps(["moon", "mon", "mooon", "mun"]), 'moon', None, None),
            (1, 'Counting to 10', 'Count from 1 to 10 with fun examples!', 'math', '<p>Count from 1 to 10 with fun examples!</p><img src="https://via.placeholder.com/300x200" alt="Numbers">', None, None, None, 'What number comes after 4?', json.dumps(["3", "5", "7", "10"]), '5', None, None),
            (1, 'Solar System Basics', 'Explore the planets in our solar system.', 'science', '<p>Explore the planets in our solar system.</p><img src="https://via.placeholder.com/300x200" alt="Planets"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', None, None, None, 'Which planet is closest to the sun?', json.dumps(["Earth", "Mars", "Mercury", "Jupiter"]), 'Mercury', None, None),
            (1, 'Addition Up to 10', 'Learn to add numbers up to 10.', 'math', '<p>Learn to add numbers up to 10.</p><img src="https://via.placeholder.com/300x200" alt="Addition">', None, None, None, 'What is 4 + 3?', json.dumps(["6", "7", "8", "5"]), '7', '7', None),
            (1, 'S Sound Phonics', 'Learn the S sound with words like sun and star.', 'language', '<p>Learn the S sound with words like <strong>sun</strong> and <strong>star</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Sun">', 'sun', '/sʌn/', 'sun', 'What is the correct spelling?', json.dumps(["sun", "son", "sunn", "sn"]), 'sun', None, None),
            (1, 'Earth Animals', 'Discover animals on Earth and beyond!', 'science', '<p>Discover animals on Earth and beyond!</p><img src="https://via.placeholder.com/300x200" alt="Animals"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', None, None, None, 'Which animal says "meow"?', json.dumps(["Dog", "Cat", "Bird", "Fish"]), 'Cat', None, None),
            (1, 'A Sound Phonics', 'Learn the A sound with words like apple and ant.', 'language', '<p>Learn the A sound with words like <strong>apple</strong> and <strong>ant</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Apple">', 'apple', '/ˈæp.əl/', 'apple', 'What is the correct spelling?', json.dumps(["apple", "aple", "appl", "aplle"]), 'apple', None, None),
            (2, 'Identifying Shapes', 'Identify different shapes: Circle, Square, Triangle.', 'math', '<p>Identify different shapes: Circle, Square, Triangle.</p><img src="https://via.placeholder.com/300x200" alt="Shapes">', None, None, None, 'How many sides does a triangle have?', json.dumps(["0", "3", "4", "Infinite"]), '3', '3', None),
            (3, 'Water Cycle Basics', 'Learn about evaporation, condensation, and precipitation.', 'science', '<p>Learn about evaporation, condensation, and precipitation.</p><img src="https://via.placeholder.com/300x200" alt="Water Cycle"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', None, None, None, 'What is the first step in the water cycle?', json.dumps(["Precipitation", "Evaporation", "Condensation", "Collection"]), 'Evaporation', None, None),
            (1, 'Basic Colors', 'Learn basic colors: Red, Blue, Green.', 'language', '<p>Learn basic colors: Red, Blue, Green.</p><img src="https://via.placeholder.com/300x200" alt="Colors">', 'red', '/rɛd/', 'red', 'What is the correct spelling?', json.dumps(["red", "read", "rd", "redd"]), 'red', None, 'hat'),
            (2, 'B Sound Phonics', 'Learn the B sound with words like book and ball.', 'language', '<p>Learn the B sound with words like <strong>book</strong> and <strong>ball</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Book">', 'book', '/bʊk/', 'book', 'What is the correct spelling?', json.dumps(["book", "buk", "boook", "bock"]), 'book', None, None),
            (3, 'Simple Fractions', 'Understand simple fractions like 1/2 and 1/4.', 'math', '<p>Understand simple fractions like 1/2 and 1/4.</p><img src="https://via.placeholder.com/300x200" alt="Fractions">', None, None, None, 'What is half of 8?', json.dumps(["3", "4", "5", "6"]), '4', '4', None),
            (2, 'Subtraction Facts', 'Subtraction: Solve 10 - 4 = ?.', 'math', '<p>Subtraction: Solve 10 - 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Subtraction">', None, None, None, 'What is 10 - 4?', json.dumps(["3", "4", "5", "6"]), '6', '6', None),
            (3, 'Multiplication Intro', 'Multiplication: Solve 3 x 4 = ?.', 'math', '<p>Multiplication: Solve 3 x 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Multiplication">', None, None, None, 'What is 3 x 4?', json.dumps(["10", "12", "15", "20"]), '12', '12', None),
            (2, 'Weather Patterns', 'Weather: Learn about snow.', 'science', '<p>Weather: Learn about snow.</p><img src="https://via.placeholder.com/300x200" alt="Weather"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', None, None, None, 'What is snow?', json.dumps(["Frozen rain", "Hot wind", "Sunlight", "Clouds"]), 'Frozen rain', None, None),
            # Updated seeds for late Sept 2025 (Grade 1-2: phonics/CVC, counting/addition, body/plants/weather)
            (1, 'Short A CVC Fun', 'Short A CVC: cat, hat, bat. Trace and spell for fluency.', 'language', '<p>Short A CVC: cat, hat, bat. Trace and spell for fluency.</p><img src="https://via.placeholder.com/300x200?text=Cat" alt="Cat">', 'cat', '/kæt/', 'cat', 'Spell the pet animal:', json.dumps(['cat', 'kat', 'ct', 'caat']), 'cat', None, 'hat'),
            (1, 'Counting Apples', 'Count to 10: Apples in a basket (1-10 grouping).', 'math', '<p>Count to 10: Apples in a basket (1-10 grouping).</p><img src="https://via.placeholder.com/300x200?text=Counting" alt="Apples">', None, None, None, 'How many apples: 5 + 2?', json.dumps(["6", "7", "8", "5"]), '7', '7', None),
            (1, 'Body Parts Basics', 'Body parts: Head, arms for moving/hugging.', 'science', '<p>Body parts: Head, arms for moving/hugging.</p><img src="https://via.placeholder.com/300x200?text=Body" alt="Body Parts">', None, None, None, 'What do arms do?', json.dumps(["See", "Hug", "Hear", "Smell"]), 'Hug', None, None),
            (2, 'ST Blend Phonics', 'ST blend: star, stop, stamp. Blend sounds.', 'language', '<p>ST blend: star, stop, stamp. Blend sounds.</p><img src="https://via.placeholder.com/300x200?text=Star" alt="Star">', 'star', '/stɑːr/', 'star', 'Spell the night sky shape:', json.dumps(['star', 'starr', 'tar', 'staar']), 'star', None, 'sky'),
            (2, 'Subtraction Within 10', 'Subtraction facts: 8 - 3, within 10.', 'math', '<p>Subtraction facts: 8 - 3, within 10.</p><img src="https://via.placeholder.com/300x200?text=Subtract" alt="Blocks">', None, None, None, 'What is 8 - 3?', json.dumps(["4", "5", "6", "7"]), '5', '5', None),
            (2, 'Plants Growth Needs', 'Plants need: Sun, water, soil for growth.', 'science', '<p>Plants need: Sun, water, soil for growth.</p><img src="https://via.placeholder.com/300x200?text=Plant" alt="Plant"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', None, None, None, 'Main need for plants?', json.dumps(["Dark", "Sun", "Wind", "Rock"]), 'Sun', None, None),
            (2, 'CR Blend Phonics', 'CR blend: crab, crop (fall harvest theme).', 'language', '<p>CR blend: crab, crop (fall harvest theme).</p><img src="https://via.placeholder.com/300x200?text=Crab" alt="Crab">', 'crab', '/kræb/', 'crab', 'Spell the sea creature:', json.dumps(['crab', 'crap', 'krab', 'crabb']), 'crab', None, 'beach')
        ]
        c.executemany("""
            INSERT OR IGNORE INTO lessons (title, description, grade, subject, content, trace_word, sound, spell_word, mc_question, mc_options, mc_answer, math_answer, sentence_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, lessons)
        conn.commit()
        logger.debug("Seeded %d lessons", len(lessons))
        print(f"Seeded {len(lessons)} lessons")
    except sqlite3.OperationalError as e:
        logger.error(f"Seed lessons failed: {str(e)}")
        print(f"Seed lessons failed: {e}")
        conn.rollback()
        raise

def check_lessons_schema(conn):
    c = conn.cursor()
    try:
        for table in ['lessons', 'lesson_responses', 'tests', 'lessons_users']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                logger.error(f"Table {table} missing")
                raise ValueError(f"Table {table} missing")
        # Check required columns in lessons - added title and description
        c.execute("PRAGMA table_info(lessons)")
        columns = [row[1] for row in c.fetchall()]
        required = ['title', 'description', 'math_answer', 'sentence_answer', 'mc_options']
        for col in required:
            if col not in columns:
                col_type = 'TEXT' if col in ['title', 'description', 'mc_options', 'sentence_answer'] else 'INTEGER' if col == 'math_answer' else 'TEXT'
                add_column_if_missing(c, 'lessons', col, col_type)
                conn.commit()
                logger.info(f"Added required column {col} to lessons table")
    except Exception as e:
        logger.error(f"Lessons schema check failed: {str(e)}")
        raise