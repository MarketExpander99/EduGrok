# EduGrok MVP

## Setup
1. `npm install`
2. Add env vars: REACT_APP_SUPABASE_URL, REACT_APP_SUPABASE_ANON_KEY, REACT_APP_CLERK_PUBLISHABLE_KEY
3. `npm start` for dev
4. Deploy to Netlify

## Supabase Tables
- posts: id SERIAL PRIMARY KEY, user TEXT, handle TEXT, date TEXT, content TEXT, likes INTEGER, retweets INTEGER, comments INTEGER
- users: id TEXT PRIMARY KEY, name TEXT, age INTEGER, parent_email TEXT, score INTEGER DEFAULT 0, grade TEXT, lessons INTEGER DEFAULT 0, games INTEGER DEFAULT 0, offline_mode BOOLEAN DEFAULT FALSE, schedule JSONB, framework TEXT
- comments: id SERIAL PRIMARY KEY, post_id INTEGER REFERENCES posts(id), user_id TEXT REFERENCES users(id), content TEXT
- lessons: id SERIAL PRIMARY KEY, user_id TEXT REFERENCES users(id), answer TEXT
- scores: id SERIAL PRIMARY KEY, user_id TEXT REFERENCES users(id), score INTEGER

Seed posts table with sample data:
```sql
INSERT INTO posts (user, handle, date, content, likes, retweets, comments) VALUES
('GrokletFanClub', '@GrokletFanClub', 'Aug 16, 2025', 'Join the EduGrok revolution! Safe, fun learning for kids worldwide with @Grok. Try the Space Invaders math game! 🌟 #EduGrok', 50, 20, 10),
('GrokEdu', '@GrokEdu', 'Aug 16, 2025', 'Count beats with EduGrok’s music-math game! Rock out at Summer Sonic, Japan! 🎶 #EduGrok', 30, 10, 5);
```

## Notes
- Optimize for low-end Android: Keep components lightweight.
- For full offline, register service worker in index.js if needed.
- Expand games/lessons as per iterations.
- New: Scheduling in Settings, framework selection in ProfileSetup, dynamic grade 4 lessons in Feed.