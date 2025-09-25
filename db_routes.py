from flask import session, redirect, url_for
import logging

logger = logging.getLogger(__name__)

from db import reset_db

def reset_db_route():
    if 'user_id' not in session:
        logger.error("Unauthorized access to /reset_db")
        return "Login required", 401
    reset_db()
    return redirect(url_for('home'))