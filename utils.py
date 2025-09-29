import re
import os

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def filter_content(content):
    # FIXED: Replacement as lambda to handle group(2) append (was function + str error)
    def replace_link(m):
        url = m.group(1)
        punct = m.group(2) or ''
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>{punct}'
    # Match URLs followed by optional punctuation (no \s* to avoid over-consuming)
    content = re.sub(r'(https?://[^\s<>"\']+)([.,;:!?]?)', replace_link, content)
    # Strip script/tags if needed (use bleach for prod)
    return content.strip()