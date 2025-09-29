import re
import os

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def filter_content(content):
    # Clean/sanitize content (e.g., embed links, strip dangerous tags)
    # Simple link embedding
    def repl(m):
        url = m.group(1)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
    content = re.sub(r'(https?://[^\s<>"\']+)', repl, content)
    # Strip script/tags if needed (use bleach for prod)
    return content.strip()