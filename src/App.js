import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { ClerkProvider, SignedIn, SignedOut, SignIn, useUser } from '@clerk/clerk-react';
import Feed from './components/Feed.jsx';
import Grading from './components/Grading.jsx';
import SpaceInvaders from './components/SpaceInvaders.jsx';
import Dashboard from './components/Dashboard.jsx';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
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
        ageGroup: (clerkUser.unsafeMetadata?.age || 6) <= 8 ? '6-8' : '9-12'
      };
      setUser(userData);
      supabase.from('users').upsert({
        id: userData.id,
        age: userData.age,
        grade: userData.grade
      }).then(({ error }) => {
        if (error) console.error('Error upserting user:', error);
      });
    }
    setLoading(false);
  }, [clerkUser, isLoaded]);

  if (loading || !isLoaded) {
    return <div className="p-4 text-center" aria-live="polite">Loading...</div>;
  }

  return (
    <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white">
          <nav className="p-4 bg-blue-600 text-white flex justify-between">
            <div>
              <Link to="/" className="mr-4 hover:underline">Home</Link>
              <Link to="/feed" className="mr-4 hover:underline">Feed</Link>
              <Link to="/grading" className="mr-4 hover:underline">Grading</Link>
              <Link to="/game" className="mr-4 hover:underline">Game</Link>
              <Link to="/dashboard" className="mr-4 hover:underline">Dashboard</Link>
            </div>
            {clerkUser && (
              <button onClick={() => window.Clerk.signOut()} className="hover:underline">Sign Out</button>
            )}
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
    </ClerkProvider>
  );
}

export default App;