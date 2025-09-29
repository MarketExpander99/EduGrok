import re
import os

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def filter_content(content):
    # FIXED: Clean regex—dropped unneeded \' in char class (raw string treats \ literal; ' needs no escape)
    def repl(m):
        url = m.group(1)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
    # Match URLs followed by optional punctuation/space
    content = re.sub(r'(https?://[^\s<>"\']+)([.,;:!?]?)\s*', repl + r'\2', content)
    # Strip script/tags if needed (use bleach for prod)
    return content.strip()