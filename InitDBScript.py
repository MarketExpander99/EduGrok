from app import app
from db import reset_db

with app.app_context():
    reset_db()
    print("DB reset complete! Tables recreated with new schema.")