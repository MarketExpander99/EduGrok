import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { ClerkProvider, SignedIn, SignedOut, SignIn, useUser } from '@clerk/clerk-react';
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
  const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || 'undefined';
  console.log('VITE_SUPABASE_URL:', supabaseUrl);
  console.log('VITE_SUPABASE_ANON_KEY:', supabaseAnonKey);
  console.log('VITE_CLERK_PUBLISHABLE_KEY:', clerkKey);
  const url = new URL(supabaseUrl);
  console.log('Validated URL:', url.href);
  const supabase = createClient(supabaseUrl, supabaseAnonKey);
  console.log('Supabase client initialized, testing with:', { url: supabaseUrl });
} catch (e) {
  console.error('Invalid URL or setup in App.jsx:', e, 'Values:', {
    VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
    VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY,
    VITE_CLERK_PUBLISHABLE_KEY: import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
  });
}

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://zahrotkjbhfegvwsevjy.supabase.co',
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InphaHJvdGtqYmhmZWd2d3Nldmp5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU1MzcwNDksImV4cCI6MjA3MTExMzA0OX0.PJHE_2uvVuixA1velpE-KPmD4o2W-UENiegcZl1wFI8'
);

function App() {
  const { user: clerkUser, isLoaded } = useUser();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isLoaded && clerkUser) {
      const userData = {
        id: clerkUser.id,
        age: clerkUser.unsafeMetadata?.age || 6,
        grade: clerkUser.unsafeMetadata?.grade || 1,
        ageGroup: (clerkUser.unsafeMetadata?.age || 6) <= 8 ? '6-8' : '9-12',
        theme: clerkUser.unsafeMetadata?.theme || 'light'
      };
      setUser(userData);
      supabase.from('users').upsert({
        id: userData.id,
        age: userData.age,
        grade: userData.grade
      }).then(({ data, error }) => {
        if (error) console.error('Error upserting user:', error, 'Response:', data);
        else console.log('User upserted:', data);
      });
    }
    setLoading(false);
  }, [clerkUser, isLoaded]);

  if (loading || !isLoaded) {
    return <div className="p-4 text-center" aria-live="polite">Loading...</div>;
  }

  return (
    <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || 'pk_test_ZGVzdGluZWQtc2F0eXItMzEuY2xlcmsuYWNjb3VudHMuZGV2JA'}>
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
                {clerkUser && (
                  <>
                    <ThemeToggle user={clerkUser} />
                    <button onClick={() => window.Clerk.signOut()} className="ml-4 hover:underline">Sign Out</button>
                  </>
                )}
              </div>
            </nav>
            <SignedIn>
              <Routes>
                <Route path="/" element={<h1 className="p-4 text-3xl">Welcome to SA Homeschool</h1>} />
                <Route path="/feed" element={user ? <Feed user={user} /> : <Navigate to="/sign-in" />} />
                <Route path="/grading" element={user ? <Grading user={user} setUser={setUser} /> : <Navigate to="/sign-in" />} />
                <Route path="/game" element={user ? <SpaceInvaders /> : <Navigate to="/sign-in" />} />
                <Route path="/dashboard" element={user ? <Dashboard user={user} /> : <Navigate to="/sign-in" />} />
                <Route path="/sign-in" element={<Navigate to="/" />} />
              </Routes>
            </SignedIn>
            <SignedOut>
              <Routes>
                <Route path="/sign-in" element={<SignIn routing="path" path="/sign-in" />} />
                <Route path="*" element={<Navigate to="/sign-in" />} />
              </Routes>
            </SignedOut>
          </div>
        </BrowserRouter>
      </ErrorBoundary>
    </ClerkProvider>
  );
}

export default App;