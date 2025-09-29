import os
import sqlite3
import logging
from flask import g

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='/tmp/db.log', level=logging.DEBUG)

from users_db import init_users_tables, seed_users, check_users_schema
from lessons_db import init_lessons_tables, check_lessons_schema, seed_lessons
from social_db import init_social_tables, seed_social_posts, seed_social_comments, check_social_schema
from achievements_db import init_achievements_tables, check_achievements_schema

# DB connection
def get_db():
    if 'db' not in g:
        default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'edugrok.db')
        if 'RENDER' in os.environ:
            db_path = '/data/edugrok.db'
            logger.debug(f"Using Render DB path: {db_path}")
            print(f"Using Render DB path: {db_path}")
        else:
            db_path = os.environ.get('DB_PATH', default_db_path)
            logger.debug(f"Using DB path: {db_path} (default: {default_db_path})")
            print(f"Using DB path: {db_path} (default: {default_db_path})")
        
        db_dir = os.path.dirname(db_path)
        if db_dir and db_dir != os.path.dirname(os.path.abspath(__file__)) and not os.path.exists(db_dir):
            try:
                parent_dir = os.path.dirname(db_dir)
                if parent_dir and not os.access(parent_dir, os.W_OK):
                    logger.error(f"Parent directory not writable: {parent_dir}")
                    print(f"Parent directory not writable: {parent_dir}")
                    raise PermissionError(f"Cannot write to {parent_dir}")
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created DB directory: {db_dir}")
                print(f"Created DB directory: {db_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating {db_dir}: {str(e)}")
                print(f"Permission denied creating {db_dir}: {e}")
                raise
        
        if not os.path.exists(db_path):
            logger.info(f"DB not found at {db_path} - creating")
            print(f"DB not found at {db_path} - creating")
            try:
                if not os.access(os.path.dirname(db_path), os.W_OK):
                    logger.error(f"Directory not writable: {os.path.dirname(db_path)}")
                    print(f"Directory not writable: {os.path.dirname(db_path)}")
                    raise PermissionError(f"Cannot write to {os.path.dirname(db_path)}")
                with open(db_path, 'a'):
                    pass
                logger.info(f"Created DB at {db_path}")
                print(f"Created DB at {db_path}")
            except PermissionError as e:
                logger.error(f"Permission denied at {db_path}: {str(e)}")
                print(f"Permission denied at {db_path}: {e}")
                raise
        
        try:
            g.db = sqlite3.connect(db_path, timeout=10)
            g.db.execute('PRAGMA journal_mode=WAL;')
            g.db.row_factory = sqlite3.Row
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to connect to DB at {db_path}: {str(e)}")
            print(f"Failed to connect to DB at {db_path}: {e}")
            raise
    return g.db

def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        logger.debug("Database connection closed")

# DB reset
def reset_db():
    conn = get_db()
    c = conn.cursor()
    try:
        drops = [
            "feedback", "badges", "user_points", "post_likes", "reposts", "comments",
            "games", "tests", "lesson_responses", "lessons_users", "lessons", "posts", "users"
        ]
        for table in drops:
            c.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        logger.info("Force reset: Dropped all tables")
        print("Dropped all tables")
        init_db()
        logger.info("Force reset complete")
        print("DB reset complete")
    except Exception as e:
        logger.error(f"DB reset failed: {str(e)}")
        print(f"DB reset failed: {e}")
        conn.rollback()
        raise

# Schema check
def check_db_schema():
    conn = get_db()
    try:
        check_users_schema(conn)
        check_lessons_schema(conn)
        check_social_schema(conn)
        check_achievements_schema(conn)
        logger.debug("Schema check passed")
        print("Schema check passed")
    except Exception as e:
        logger.error(f"Schema check failed: {str(e)}")
        raise

# Initialize DB
def init_db():
    conn = get_db()
    c = conn.cursor()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchall()[0][2]
        logger.debug(f"Initializing DB at {db_path}")
        print(f"Initializing DB at {db_path}")
        
        init_users_tables(conn)
        init_lessons_tables(c)
        init_social_tables(c)
        init_achievements_tables(c)
        
        # Seed bot users
        skykidz_id, grokedu_id = seed_users(conn)
        if skykidz_id is None or grokedu_id is None:
            logger.error("Failed to retrieve bot user IDs. SkyKidz ID: %s, GrokEdu ID: %s", skykidz_id, grokedu_id)
            c.execute("SELECT email, id FROM users")
            users = c.fetchall()
            logger.debug("Current users in DB: %s", [(row[0], row[1]) for row in users])
            raise ValueError(f"Bot user insertion failed. SkyKidz ID: {skykidz_id}, GrokEdu ID: {grokedu_id}")

        logger.debug("Bot user IDs: SkyKidz=%s, GrokEdu=%s", skykidz_id, grokedu_id)
        print(f"Bot user IDs: SkyKidz={skykidz_id}, GrokEdu={grokedu_id}")

        # Seed bot posts
        post1_id, post2_id, post3_id, post4_id, post5_id = seed_social_posts(c, skykidz_id, grokedu_id)
        if post1_id and post2_id and post3_id and post4_id and post5_id:
            seed_social_comments(c, skykidz_id, grokedu_id, post1_id, post2_id, post3_id, post4_id, post5_id)
        
        # FIXED: Seed lessons on init (not just reset)
        seed_lessons(conn)
        logger.info("Lessons seeded on init")
        print("Lessons seeded on init")
        
        conn.commit()
        logger.info("Tables created/updated")
        print("Tables created/updated")
        logger.info("Bot users inserted")
        print("Bot users inserted")
        logger.info("Bot posts seeded")
        print("Bot posts seeded")
        logger.info("Bot comments seeded")
        print("Bot comments seeded")

    except sqlite3.Error as e:
        logger.error(f"SQLite error in init_db: {str(e)}")
        print(f"SQLite error in init_db: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"DB init failed: {str(e)}")
        print(f"DB init failed: {e}")
        conn.rollback()
        raise