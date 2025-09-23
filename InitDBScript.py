from flask import Flask
from db import init_db, seed_lessons, check_db_schema

app = Flask(__name__)

with app.app_context():
    try:
        init_db()
        check_db_schema()
        seed_lessons()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {str(e)}")