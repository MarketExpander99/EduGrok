from flask import session, request, jsonify, redirect, url_for, render_template
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from db import get_db

def phonics_game():
    logger.debug("Phonics game route")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        grade = session.get('grade', 1)
        language = session.get('language', 'en')
        # Define phonics word lists by grade
        word_lists = {
            1: {
                'en': [
                    {'word': 'cat', 'sound': '/kæt/'},
                    {'word': 'dog', 'sound': '/dɒɡ/'},
                    {'word': 'sun', 'sound': '/sʌn/'},
                    {'word': 'moon', 'sound': '/muːn/'}
                ],
                'bilingual': [
                    {'word': 'cat', 'sound': '/kæt/', 'af': 'kat', 'af_sound': '/kat/'},
                    {'word': 'dog', 'sound': '/dɒɡ/', 'af': 'hond', 'af_sound': '/ɦɔnt/'},
                    {'word': 'sun', 'sound': '/sʌn/', 'af': 'son', 'af_sound': '/sɔn/'},
                    {'word': 'moon', 'sound': '/muːn/', 'af': 'maan', 'af_sound': '/mɑːn/'}
                ]
            },
            2: {
                'en': [
                    {'word': 'ship', 'sound': '/ʃɪp/'},
                    {'word': 'fish', 'sound': '/fɪʃ/'},
                    {'word': 'tree', 'sound': '/triː/'},
                    {'word': 'bird', 'sound': '/bɜːrd/'}
                ],
                'bilingual': [
                    {'word': 'ship', 'sound': '/ʃɪp/', 'af': 'skip', 'af_sound': '/skɪp/'},
                    {'word': 'fish', 'sound': '/fɪʃ/', 'af': 'vis', 'af_sound': '/fɪs/'},
                    {'word': 'tree', 'sound': '/triː/', 'af': 'boom', 'af_sound': '/bʊəm/'},
                    {'word': 'bird', 'sound': '/bɜːrd/', 'af': 'voël', 'af_sound': '/fuəl/'}
                ]
            },
            3: {
                'en': [
                    {'word': 'house', 'sound': '/haʊs/'},
                    {'word': 'cloud', 'sound': '/klaʊd/'},
                    {'word': 'spoon', 'sound': '/spuːn/'},
                    {'word': 'train', 'sound': '/treɪn/'}
                ],
                'bilingual': [
                    {'word': 'house', 'sound': '/haʊs/', 'af': 'huis', 'af_sound': '/ɦœɪs/'},
                    {'word': 'cloud', 'sound': '/klaʊd/', 'af': 'wolk', 'af_sound': '/vɔlk/'},
                    {'word': 'spoon', 'sound': '/spuːn/', 'af': 'lepel', 'af_sound': '/lɪəpəl/'},
                    {'word': 'train', 'sound': '/treɪn/', 'af': 'trein', 'af_sound': '/trɛɪn/'}
                ]
            }
        }
        timer_duration = 60 if grade == 1 else 45 if grade == 2 else 30
        words = word_lists[grade][language]

        if request.method == 'POST':
            score = int(request.get_json().get('score', 0))
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO games (user_id, score) VALUES (?, ?)", (session['user_id'], score))
            c.execute("SELECT COUNT(*) FROM games WHERE user_id = ?", (session['user_id'],))
            game_count = c.fetchone()[0]
            if game_count >= 5:
                c.execute("INSERT OR IGNORE INTO badges (user_id, badge_name, awarded_date) VALUES (?, ?, ?)", 
                         (session['user_id'], 'Phonics Pro', datetime.now().isoformat()))
            conn.commit()
            logger.info(f"User {session['user_id']} completed phonics game with score {score}")
            return jsonify({'success': True})

        logger.info(f"User {session['user_id']} accessed phonics game, grade {grade}, language {language}")
        return render_template('phonics_game.html.j2', 
                             theme=session.get('theme', 'astronaut'), 
                             grade=grade, 
                             language=language, 
                             words=words, 
                             timer_duration=timer_duration)
    except Exception as e:
        logger.error(f"Phonics game failed: {str(e)}")
        return render_template('error.html.j2', error=f"Failed to load phonics game: {str(e)}", 
                             theme=session.get('theme', 'astronaut'), 
                             language=session.get('language', 'en')), 500