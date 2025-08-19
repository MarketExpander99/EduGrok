# Codebase File List

| File | Version | Description |
|------|---------|-------------|
| index.html | 2.1.0 | Main HTML entry point with SEO meta tags |
| vite.config.js | 1.0.0 | Vite configuration for React build |
| src/main.jsx | 1.0.0 | React app entry point |
| src/App.jsx | 1.1.0 | Main app component with improved Clerk integration and routing |
| src/components/Feed.jsx | 1.1.0 | Feed component with enhanced child safety and weighted shuffle |
| src/components/Grading.jsx | 1.1.0 | Grading component with answer feedback and quiz result storage |
| src/components/SpaceInvaders.jsx | 1.1.0 | Space Invaders game with scoring and Supabase integration |
| src/index.css | 1.1.0 | Global CSS with Tailwind directives |
| netlify.toml | 1.0.0 | Netlify configuration for deployment |
| CODEBASE.md | 1.1.0 | File list and version tracking with changelog |

## Changelog
- **index.html (2.1.0)**: Added meta tags for SEO and favicon placeholder.
- **src/App.jsx (1.1.0)**: Switched to `useUser` for Clerk, added `Navigate` for protected routes.
- **src/components/Feed.jsx (1.1.0)**: Improved child safety with allowlist, added pagination and error handling.
- **src/components/Grading.jsx (1.1.0)**: Added answer feedback and quiz result storage in Supabase.
- **src/components/SpaceInvaders.jsx (1.1.0)**: Added score tracking, game over state, and Supabase score storage.
- **src/index.css (1.1.0)**: Added Tailwind directives.
- **netlify.toml (1.0.0)**: Added for Netlify deployment configuration.
- **CODEBASE.md (1.1.0)**: Added changelog section.