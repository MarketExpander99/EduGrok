import logging
import sqlite3

logger = logging.getLogger(__name__)

def init_lessons_tables(c):
    try:
        # Drop and recreate lessons table to ensure new columns are included
        c.execute('''CREATE TABLE IF NOT EXISTS lessons 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, 
                      subject TEXT, content TEXT, completed BOOLEAN DEFAULT 0, 
                      trace_word TEXT, sound TEXT, spell_word TEXT, mc_question TEXT, 
                      mc_options TEXT, mc_answer TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS tests 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, grade INTEGER, score INTEGER, date TEXT,
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS lesson_responses 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id INTEGER, user_id INTEGER, activity_type TEXT, response TEXT, is_correct BOOLEAN, points INTEGER,
                      FOREIGN KEY (lesson_id) REFERENCES lessons(id), FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_lessons_user_grade_completed ON lessons(user_id, grade, completed)')
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
            (None, 1, 'language', '<p>Learn the M sound with words like <strong>moon</strong> and <strong>mars</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Moon"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, 'moon', '/mu?n/', 'moon', 'What is the correct spelling?', '["moon", "mon", "mooon", "mun"]', 'moon'),
            (None, 1, 'math', '<p>Count from 1 to 10 with fun examples!</p><img src="https://via.placeholder.com/300x200" alt="Numbers">', 0, None, None, None, 'What number comes after 4?', '["3", "5", "7", "10"]', '5'),
            (None, 1, 'science', '<p>Explore the planets in our solar system.</p><img src="https://via.placeholder.com/300x200" alt="Planets"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'Which planet is closest to the sun?', '["Earth", "Mars", "Mercury", "Jupiter"]', 'Mercury'),
            (None, 1, 'math', '<p>Learn to add numbers up to 10.</p><img src="https://via.placeholder.com/300x200" alt="Addition">', 0, None, None, None, 'What is 4 + 3?', '["6", "7", "8", "5"]', '7'),
            (None, 1, 'language', '<p>Learn the S sound with words like <strong>sun</strong> and <strong>star</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Sun">', 0, 'sun', '/s?n/', 'sun', 'What is the correct spelling?', '["sun", "son", "sunn", "sn"]', 'sun'),
            (None, 1, 'science', '<p>Discover animals on Earth and beyond!</p><img src="https://via.placeholder.com/300x200" alt="Animals"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'Which animal says "meow"?', '["Dog", "Cat", "Bird", "Fish"]', 'Cat'),
            (None, 1, 'language', '<p>Learn the A sound with words like <strong>apple</strong> and <strong>ant</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Apple">', 0, 'apple', '/æp.?l/', 'apple', 'What is the correct spelling?', '["apple", "aple", "appl", "aplle"]', 'apple'),
            (None, 2, 'math', '<p>Identify different shapes: Circle, Square, Triangle.</p><img src="https://via.placeholder.com/300x200" alt="Shapes">', 0, None, None, None, 'How many sides does a triangle have?', '["0", "3", "4", "Infinite"]', '3'),
            (None, 3, 'science', '<p>Learn about evaporation, condensation, and precipitation.</p><img src="https://via.placeholder.com/300x200" alt="Water Cycle"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'What is the first step in the water cycle?', '["Precipitation", "Evaporation", "Condensation", "Collection"]', 'Evaporation'),
            (None, 1, 'language', '<p>Learn basic colors: Red, Blue, Green.</p><img src="https://via.placeholder.com/300x200" alt="Colors">', 0, 'red', '/r?d/', 'red', 'What is the correct spelling?', '["red", "read", "rd", "redd"]', 'red'),
            (None, 2, 'language', '<p>Learn the B sound with words like <strong>book</strong> and <strong>ball</strong>.</p><img src="https://via.placeholder.com/300x200" alt="Book">', 0, 'book', '/b?k/', 'book', 'What is the correct spelling?', '["book", "buk", "boook", "bock"]', 'book'),
            (None, 3, 'math', '<p>Understand simple fractions like 1/2 and 1/4.</p><img src="https://via.placeholder.com/300x200" alt="Fractions">', 0, None, None, None, 'What is half of 8?', '["3", "4", "5", "6"]', '4'),
            (None, 2, 'math', '<p>Subtraction: Solve 10 - 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Subtraction">', 0, None, None, None, 'What is 10 - 4?', '["3", "4", "5", "6"]', '6'),
            (None, 3, 'math', '<p>Multiplication: Solve 3 x 4 = ?</p><img src="https://via.placeholder.com/300x200" alt="Multiplication">', 0, None, None, None, 'What is 3 x 4?', '["10", "12", "15", "20"]', '12'),
            (None, 2, 'science', '<p>Weather: Learn about snow.</p><img src="https://via.placeholder.com/300x200" alt="Weather"><video src="https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4" controls width="300"></video>', 0, None, None, None, 'What is snow?', '["Frozen rain", "Hot wind", "Sunlight", "Clouds"]', 'Frozen rain')
        ]
        c.executemany("""
            INSERT OR IGNORE INTO lessons (user_id, grade, subject, content, completed, trace_word, sound, spell_word, mc_question, mc_options, mc_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        for table in ['lessons', 'lesson_responses', 'tests']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                logger.error(f"Table {table} missing")
                raise ValueError(f"Table {table} missing")
    except Exception as e:
        logger.error(f"Lessons schema check failed: {str(e)}")
        raise