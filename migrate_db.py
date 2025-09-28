# migrate_lessons.py
# Run this with: python migrate_lessons.py
# This script migrates the old lessons schema to the new global lessons + lessons_users setup.
# It assumes the DB is at the default path from db.py. Backup your DB first!
# After running, update your app.py to use the new init_lessons_tables (without DROPs).

import sqlite3
import json
import logging
from db import get_db  # Assumes db.py is in the same dir with get_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_lessons():
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Step 1: Check if old lessons table exists and has user_id/completed
        c.execute("PRAGMA table_info(lessons)")
        old_columns = [row[1] for row in c.fetchall()]
        if 'user_id' in old_columns and 'completed' in old_columns:
            logger.info("Detected old lessons schema. Starting migration...")
            
            # Step 2: Create new lessons table (global)
            c.execute('''CREATE TABLE IF NOT EXISTS new_lessons 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, grade INTEGER, 
                          subject TEXT, content TEXT, 
                          trace_word TEXT, sound TEXT, spell_word TEXT, mc_question TEXT, 
                          mc_options TEXT, mc_answer TEXT, math_answer TEXT, sentence_answer TEXT,
                          UNIQUE(grade, subject, content))''')  # UNIQUE to dedup
            
            # Step 3: Create lessons_users if missing
            c.execute('''CREATE TABLE IF NOT EXISTS lessons_users 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          user_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL, 
                          completed BOOLEAN DEFAULT 0, 
                          assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY (user_id) REFERENCES users(id), 
                          FOREIGN KEY (lesson_id) REFERENCES new_lessons(id),
                          UNIQUE(user_id, lesson_id))''')
            
            # Step 4: Migrate unique lessons to new_lessons
            c.execute('''INSERT OR IGNORE INTO new_lessons 
                         (grade, subject, content, trace_word, sound, spell_word, 
                          mc_question, mc_options, mc_answer, math_answer, sentence_answer)
                         SELECT DISTINCT grade, subject, content, trace_word, sound, spell_word, 
                                        mc_question, mc_options, mc_answer, math_answer, sentence_answer
                         FROM lessons''')
            new_lesson_count = c.rowcount
            logger.info(f"Migrated {new_lesson_count} unique lessons to new_lessons")
            
            # Step 5: Map old lesson_ids to new (for each old lesson, find matching new_id)
            c.execute('''CREATE TEMP TABLE lesson_map AS
                         SELECT old_l.id AS old_id, new_l.id AS new_id
                         FROM lessons old_l
                         JOIN new_lessons new_l ON (old_l.grade = new_l.grade 
                                                   AND old_l.subject = new_l.subject 
                                                   AND old_l.content = new_l.content)''')
            
            # Step 6: Insert into lessons_users with completed from old
            c.execute('''INSERT INTO lessons_users (user_id, lesson_id, completed)
                         SELECT old_l.user_id, map.new_id, old_l.completed
                         FROM lessons old_l
                         JOIN lesson_map map ON old_l.id = map.old_id
                         WHERE old_l.user_id IS NOT NULL''')
            user_lesson_count = c.rowcount
            logger.info(f"Created {user_lesson_count} user-lesson assignments")
            
            # Step 7: Drop old lessons and rename new_lessons to lessons
            c.execute('DROP TABLE lessons')
            c.execute('ALTER TABLE new_lessons RENAME TO lessons')
            
            # Step 8: Clean up temp
            c.execute('DROP TABLE lesson_map')
            
            # Step 9: Update lesson_responses to point to new lesson_ids (if any old refs)
            c.execute('''UPDATE lesson_responses 
                         SET lesson_id = (SELECT new_id FROM lesson_map lm WHERE lm.old_id = lesson_responses.lesson_id)
                         WHERE lesson_id IN (SELECT old_id FROM lesson_map)''')
            
            conn.commit()
            logger.info("Migration complete! New schema: global lessons + lessons_users.")
            
        else:
            logger.info("New schema already in place. No migration needed.")
        
        # Step 10: Re-seed any missing lessons (from lessons_db.py seed_lessons, but simplified here)
        from lessons_db import seed_lessons  # Assumes lessons_db.py in same dir
        seed_lessons(conn)
        conn.commit()
        logger.info("Seeding complete.")
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error during migration: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_lessons()
    print("Migration script finished. Restart your app to use the new schema.")