# add_profile_picture.py - One-time migration to add profile_picture column
import sys
sys.path.append('/workspaces/EduGrok')  # Adjust if your path differs

from app import app  # Import the Flask app
from db import get_db

def migrate():
    with app.app_context():  # This sets up the required Flask context
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in c.fetchall()]
            if 'profile_picture' not in columns:
                c.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT")
                conn.commit()
                print("Added profile_picture column to users table")
                # Set default empty string for existing rows
                c.execute("UPDATE users SET profile_picture = '' WHERE profile_picture IS NULL")
                conn.commit()
                print("Updated existing rows with default profile_picture")
            else:
                print("profile_picture column already exists")
        except Exception as e:
            print(f"Migration failed: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    migrate()
    print("Migration complete! Restart your app and test /profile or /home.")