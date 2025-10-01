# db_fix.py
import sqlite3
import os
from datetime import datetime
import json

# Path to your database (adjust if needed, based on your db.py logic)
db_path = 'edugrok.db'  # or os.path.join(os.path.dirname(__file__), 'edugrok.db')

def recreate_lessons_tables():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Drop existing tables if they exist (backup first if needed!)
    tables_to_drop = ['lesson_responses', 'lessons_users', 'completed_lessons', 'lessons']
    for table in reversed(tables_to_drop):  # Drop in reverse dependency order
        try:
            c.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Dropped table: {table}")
        except Exception as e:
            print(f"Error dropping {table}: {e}")
    
    # Recreate tables
    c.execute('''CREATE TABLE lessons 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  grade INTEGER, 
                  subject TEXT, 
                  content TEXT, 
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
    
    c.execute('''CREATE TABLE completed_lessons 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  lesson_id INTEGER, 
                  completed_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(id), 
                  FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
    
    c.execute('''CREATE TABLE lessons_users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  lesson_id INTEGER, 
                  completed INTEGER DEFAULT 0,
                  assigned_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(id), 
                  FOREIGN KEY (lesson_id) REFERENCES lessons(id))''')
    
    c.execute('''CREATE TABLE lesson_responses 
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
    
    conn.commit()
    print("Tables recreated successfully!")
    
    # Seed lessons
    now = datetime.now().isoformat()
    lessons_data = [
        (1, 'math', 'Lesson 1: Counting to 10', now, None, None, None, None, None, None, None, None, None, 'What is 2 + 3?', '5'),
        (1, 'language', 'Lesson 2: Alphabet ABC', now, 'abc', 'abc', '/æb si/', 'What is the first letter?', json.dumps(['a', 'b', 'c']), 'a', 'The ___ is the first letter.', json.dumps(['abc', 'def', 'a']), 'a', None, None),
        (1, 'science', 'Lesson 3: Colors of the Rainbow', now, None, None, None, 'What color is the sky?', json.dumps(['blue', 'red', 'green']), 'blue', None, None, None, None, None),
        (1, 'language', 'Lesson 4: Phonics A', now, 'a', 'a', '/æ/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 5: Phonics B', now, 'b', 'b', '/bi/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 6: Phonics C', now, 'c', 'c', '/si/', None, None, None, None, None, None, None, None),
        (1, 'language', 'Lesson 49: Sentence Cat on Mat', now, 'cat', 'cat', '/kæt/', 'What is the correct spelling?', json.dumps(['cat', 'kat', 'ct']), 'cat', 'The cat sat on the ___.', json.dumps(['mat', 'dog', 'moon']), 'mat', None, None),
    ]
    
    for values in lessons_data:
        c.execute("""INSERT INTO lessons 
                     (grade, subject, content, created_at, trace_word, spell_word, sound, mc_question, mc_options, mc_answer, 
                      sentence_question, sentence_options, sentence_answer, math_question, math_answer) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
    
    conn.commit()
    print("Lessons seeded successfully!")
    conn.close()

if __name__ == '__main__':
    print(f"Fixing DB at {db_path}...")
    recreate_lessons_tables()
    print("DB fixed! You can now run your app.")