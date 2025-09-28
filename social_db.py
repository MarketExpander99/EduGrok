import logging
import sqlite3

logger = logging.getLogger(__name__)

def init_social_tables(c):
    try:
        # Drop and recreate posts table to ensure correct schema
        c.execute('''CREATE TABLE IF NOT EXISTS posts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, handle TEXT, content TEXT, 
                      subject TEXT, grade INTEGER, likes INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, media_url TEXT, views INTEGER DEFAULT 0, reposts INTEGER DEFAULT 0, repost_of INTEGER,
                      FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (repost_of) REFERENCES posts(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS post_likes 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER,
                      FOREIGN KEY (post_id) REFERENCES posts(id), FOREIGN KEY (user_id) REFERENCES users(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS reposts 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, post_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (post_id) REFERENCES posts(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS comments 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, user_id INTEGER, content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (post_id) REFERENCES posts(id), 
                      FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_id ON posts(id DESC)')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_unique ON posts(user_id, content)')
        
        # Remove any duplicate comments before creating unique index
        c.execute('''
            DELETE FROM comments
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM comments
                GROUP BY post_id, user_id, content
            )
        ''')
        deleted = c.rowcount
        if deleted > 0:
            logger.info(f"Removed {deleted} duplicate comments")
            print(f"Removed {deleted} duplicate comments")
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_comments_unique ON comments(post_id, user_id, content)')
    except sqlite3.Error as e:
        logger.error(f"Error initializing social tables: {e}")
        raise

def seed_social_posts(c, skykidz_id, grokedu_id):
    try:
        bot_posts = [
            (skykidz_id, 'SkyKidz', 'Check out this fun farm math adventure! 2 cows + 3 chickens = ?', 'math', 1, 5, None, 0, 0),
            (grokedu_id, 'GrokEdu', 'Explore the solar system: Name a planet close to the sun.', 'science', 2, 10, None, 0, 0),
            (skykidz_id, 'SkyKidz', 'What color is the sky? Let\'s learn about colors!', 'language', 1, 3, None, 0, 0),
            (grokedu_id, 'GrokEdu', 'Simple subtraction: 5 apples minus 2 = ?', 'math', 2, 7, None, 0, 0),
            (skykidz_id, 'SkyKidz', 'Animals on the farm: Which one says moo?', 'science', 1, 4, None, 0, 0),
        ]
        c.executemany("INSERT OR IGNORE INTO posts (user_id, handle, content, subject, grade, likes, media_url, views, reposts, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))", bot_posts)
        
        # Fetch seeded post IDs
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%farm math%'", (skykidz_id,))
        row = c.fetchone()
        post1_id = row['id'] if row else None
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%solar system%'", (grokedu_id,))
        row = c.fetchone()
        post2_id = row['id'] if row else None
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%color is the sky%'", (skykidz_id,))
        row = c.fetchone()
        post3_id = row['id'] if row else None
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%Simple subtraction%'", (grokedu_id,))
        row = c.fetchone()
        post4_id = row['id'] if row else None
        c.execute("SELECT id FROM posts WHERE user_id = ? AND content LIKE '%Animals on the farm%'", (skykidz_id,))
        row = c.fetchone()
        post5_id = row['id'] if row else None
        
        return post1_id, post2_id, post3_id, post4_id, post5_id
    except sqlite3.Error as e:
        logger.error(f"Error seeding social posts: {e}")
        raise

def seed_social_comments(c, skykidz_id, grokedu_id, post1_id, post2_id, post3_id, post4_id, post5_id):
    try:
        bot_comments = [
            # Comments for post1
            (post1_id, skykidz_id, 'This is fun!'),
            (post1_id, grokedu_id, 'Love the math adventure!'),
            # Comments for post2
            (post2_id, skykidz_id, 'Mercury?'),
            (post2_id, grokedu_id, 'Great question!'),
            # Comments for post3
            (post3_id, grokedu_id, 'Blue!'),
            (post3_id, skykidz_id, 'Yes, blue sky!'),
            # Comments for post4
            (post4_id, skykidz_id, '3 apples left!'),
            (post4_id, grokedu_id, 'Correct!'),
            # Comments for post5
            (post5_id, grokedu_id, 'The cow!'),
            (post5_id, skykidz_id, 'Moo moo!'),
        ]
        c.executemany("INSERT OR IGNORE INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, datetime('now'))", bot_comments)
    except sqlite3.Error as e:
        logger.error(f"Error seeding social comments: {e}")
        raise

def check_social_schema(conn):
    c = conn.cursor()
    try:
        # Check posts table for media_url, views, and reposts
        c.execute("PRAGMA table_info(posts)")
        columns = {col[1]: col[2] for col in c.fetchall()}
        if 'media_url' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN media_url TEXT")
            conn.commit()
            logger.info("Added media_url column to posts table")
            print("Added media_url column to posts table")
        if 'views' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added views column to posts table")
            print("Added views column to posts table")
        if 'reposts' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN reposts INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Added reposts column to posts table")
            print("Added reposts column to posts table")
        if 'repost_of' not in columns:
            c.execute("ALTER TABLE posts ADD COLUMN repost_of INTEGER")
            conn.commit()
            logger.info("Added repost_of column to posts table")
            print("Added repost_of column to posts table")
        
        for table in ['post_likes', 'reposts', 'comments']:
            c.execute(f"PRAGMA table_info({table})")
            if not c.fetchall():
                logger.error(f"Table {table} missing")
                raise ValueError(f"Table {table} missing")
    except Exception as e:
        logger.error(f"Social schema check failed: {str(e)}")
        raise