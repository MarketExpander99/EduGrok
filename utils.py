import re

BAD_WORDS = ['bad', 'word']

def filter_content(content):
    if not isinstance(content, str):
        return ""
    for word in BAD_WORDS:
        content = re.sub(rf'\b{word}\b', '***', content, flags=re.IGNORECASE)
    return content

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'mp4'}

def embed_links(content):
    # YouTube
    youtube_regex = r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
    match = re.search(youtube_regex, content)
    if match:
        video_id = match.group(1)
        embed = f'<iframe width="300" height="200" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
        content = re.sub(youtube_regex, embed, content, count=1)
    
    # Rumble
    rumble_regex = r'https?://rumble\.com/v([a-zA-Z0-9_-]+)'
    match = re.search(rumble_regex, content)
    if match:
        video_id = match.group(1)
        embed = f'<iframe width="300" height="200" src="https://rumble.com/embed/{video_id}/" frameborder="0" allowfullscreen></iframe>'
        content = re.sub(rumble_regex, embed, content, count=1)
    
    return content