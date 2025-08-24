import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { useSupabaseAuth } from './hooks/useSupabaseAuth'; // Custom hook (see below)
import Feed from './components/Feed.jsx';
import Grading from './components/Grading.jsx';
import SpaceInvaders from './components/SpaceInvaders.jsx';
import Dashboard from './components/Dashboard.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import ThemeToggle from './components/ThemeToggle.jsx';

// Enhanced debug logs
console.log('App.jsx - Checking environment variables:');
try {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'undefined';
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'undefined';
  console.log('VITE_SUPABASE_URL:', supabaseUrl);
  console.log('VITE_SUPABASE_ANON_KEY:', supabaseAnonKey);
  const url = new URL(supabaseUrl);
  console.log('Validated URL:', url.href);
} catch (e) {
  console.error('Invalid URL in App.jsx:', e, 'Values:', {
    VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
    VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY
  });
}

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://fallback.supabase.co',
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'fallback-anon-key'
);

function App() {
  const { user, isLoaded, error } = useSupabaseAuth();
  const [localUser, setLocalUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (error) {
      console.error('Supabase Auth error:', error.message);
      return;
    }
    if (isLoaded && user) {
      const userData = {
        id: user.id,
        email: user.email || null,
        age: user.user_metadata?.age || 6,
        grade: user.user_metadata?.grade || 1,
      };
      setLocalUser(userData);
      const upsertUrl = `${supabaseUrl}/rest/v1/users?upsert=true`;
      console.log('Upsert URL:', upsertUrl);
      supabase.from('users').upsert({
        id: userData.id,
        email: userData.email,
        age: userData.age,
        grade: userData.grade
      }).then(({ error }) => {
        if (error) console.error('Error upserting user:', error.message, 'URL:', upsertUrl);
      });
    }
    setLoading(false);
  }, [user, isLoaded, error]);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setLocalUser(null);
    window.location.href = '/';
  };

  if (loading || !isLoaded) {
    return <div className="p-4 text-center" aria-live="polite">Loading...</div>;
  }

  if (error) {
    console.error('Rendering with Supabase error:', error.message);
    return <div className="p-4 text-center text-red-500">Error: {error.message}</div>;
  }

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white">
          <nav className="p-4 bg-blue-600 text-white flex justify-between items-center">
            <div>
              <Link to="/" className="mr-4 hover:underline">Home</Link>
              <Link to="/feed" className="mr-4 hover:underline">Feed</Link>
              <Link to="/grading" className="mr-4 hover:underline">Grading</Link>
              <Link to="/game" className="mr-4 hover:underline">Game</Link>
              <Link to="/dashboard" className="mr-4 hover:underline">Dashboard</Link>
            </div>
            <div className="flex items-center">
              {user && (
                <>
                  <ThemeToggle user={user} />
                  <button onClick={handleSignOut} className="ml-4 hover:underline">Sign Out</button>
                </>
              )}
            </div>
          </nav>
          {user ? (
            <Routes>
              <Route path="/" element={<h1 className="p-4 text-3xl">Welcome to SA Homeschool</h1>} />
              <Route path="/feed" element={localUser ? <Feed user={localUser} /> : <Navigate to="/" />} />
              <Route path="/grading" element={localUser ? <Grading user={localUser} setUser={setLocalUser} /> : <Navigate to="/" />} />
              <Route path="/game" element={localUser ? <SpaceInvaders /> : <Navigate to="/" />} />
              <Route path="/dashboard" element={localUser ? <Dashboard user={localUser} /> : <Navigate to="/" />} />
            </Routes>
          ) : (
            <Routes>
              <Route path="/sign-in" element={<SignIn />} />
              <Route path="*" element={<Navigate to="/sign-in" />} />
            </Routes>
          )}
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;