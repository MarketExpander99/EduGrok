import logging
import sqlite3
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

def init_social_tables(c):
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            subject TEXT DEFAULT 'General',
            media_url TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            reposts INTEGER DEFAULT 0,
            original_post_id INTEGER,  -- FIXED: For repost tracking
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (original_post_id) REFERENCES posts(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS post_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            UNIQUE(user_id, post_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS reposts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,  -- Original post ID
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            UNIQUE(user_id, post_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )''')
        logger.info("Social tables initialized")
    except sqlite3.Error as e:
        logger.error(f"Error creating social tables: {e}")
        raise

def seed_social_posts(c, skykidz_id, grokedu_id):
    try:
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (skykidz_id, "Hello from SkyKidz! Learning math is fun! #math", "math"))
        post1_id = c.lastrowid
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (grokedu_id, "GrokEdu tip: Practice language daily! #language", "language"))
        post2_id = c.lastrowid
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (skykidz_id, "Science experiment: What floats? #science", "science"))
        post3_id = c.lastrowid
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (grokedu_id, "Quick math puzzle: 2+2? Share answers! #math", "math"))
        post4_id = c.lastrowid
        c.execute("INSERT INTO posts (user_id, content, subject) VALUES (?, ?, ?)", (skykidz_id, "Favorite word of the day? Mine is 'adventure'! #language", "language"))
        post5_id = c.lastrowid
        # FIXED: Local commit for safety
        c.connection.commit()
        logger.info("Seeded bot posts")
        return post1_id, post2_id, post3_id, post4_id, post5_id
    except Exception as e:
        logger.error(f"Seed social posts failed: {e}")
        c.connection.rollback()
        raise

def seed_social_comments(c, skykidz_id, grokedu_id, post1_id, post2_id, post3_id, post4_id, post5_id):
    try:
        comments_data = [
            (skykidz_id, post1_id, "Thanks! Math rocks!"),
            (grokedu_id, post1_id, "Agreed, keep practicing!"),
            (grokedu_id, post2_id, "Daily practice is key!"),
            (skykidz_id, post3_id, "Balloons float!"),
            (grokedu_id, post4_id, "4! Easy one."),
            (skykidz_id, post5_id, "Mine is 'grok'! 😊")
        ]
        for user_id, post_id, content in comments_data:
            c.execute("INSERT INTO comments (user_id, post_id, content) VALUES (?, ?, ?)", (user_id, post_id, content))
        # FIXED: Local commit for safety
        c.connection.commit()
        logger.info("Seeded bot comments")
    except Exception as e:
        logger.error(f"Seed social comments failed: {e}")
        c.connection.rollback()
        raise

def check_social_schema(conn):
    c = conn.cursor()
    try:
        for table in ['posts', 'post_likes', 'reposts', 'comments']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                raise ValueError(f"Table {table} missing")
        # FIXED: Migrate/add original_post_id if missing
        c.execute("PRAGMA table_info(posts)")
        columns = [col[1] for col in c.fetchall()]
        if 'original_post_id' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN original_post_id INTEGER")
            conn.commit()
            logger.info("Added original_post_id to posts")
        logger.debug("Social schema check passed")
    except Exception as e:
        logger.error(f"Social schema check failed: {str(e)}")
        raise