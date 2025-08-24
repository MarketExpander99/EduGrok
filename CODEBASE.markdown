Codebase File List



File
Version
Description



index.html
2.5.0
Main HTML entry point with fixed DOCTYPE and script block


vite.config.js
1.0.0
Vite configuration for React build


src/main.jsx
1.1.0
React app entry point with updated App.jsx import


src/App.jsx
2.3.0
Main app component with Supabase Auth integration


src/components/Feed.jsx
1.2.0
Feed component with drag-and-drop support


src/components/Grading.jsx
1.1.0
Grading component with answer feedback and quiz result storage


src/components/SpaceInvaders.jsx
1.1.0
Space Invaders game with scoring and Supabase integration


src/components/Dashboard.jsx
1.4.0
Dashboard component for LearnCoins and progress with URL logging


src/components/ErrorBoundary.jsx
1.0.0
Error boundary for catching runtime errors


src/components/ThemeToggle.jsx
1.0.0
Theme toggle component for light/dark mode


src/components/SignIn.jsx
1.0.0
Sign-in component with Supabase Auth


src/hooks/useSupabaseAuth.js
1.0.0
Custom hook for Supabase Auth state management


src/index.css
1.2.0
Global CSS with Tailwind directives and dark mode support


netlify.toml
1.1.0
Netlify configuration with corrected environment variables


create_tables.sql
1.1.0
SQL script to create Supabase tables and RLS policies with fixed UUID casts


insert_feed_data.sql
1.0.0
SQL script to insert sample feed data


insert_users_data.sql
1.1.0
SQL script to insert test users with email


package.json
1.3.0
Project configuration with Supabase Auth and removed Clerk


CODEBASE.md
3.8.0
File list and version tracking with changelog


Changelog

src/App.jsx (2.3.0): Replaced Clerk with Supabase Auth integration.
src/components/SignIn.jsx (1.0.0): Added new sign-in component for Supabase Auth.
src/hooks/useSupabaseAuth.js (1.0.0): Added custom hook for Supabase Auth state.
package.json (1.3.0): Removed Clerk dependency, updated for Supabase Auth.
CODEBASE.md (3.8.0): Updated file list and versions for Supabase Auth migration.
