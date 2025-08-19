import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import {  useAuth } from '@clerk/clerk-react';
import Home from './components/Home';
import Feed from './components/Feed';
import Profile from './components/Profile';
import ProfileSetup from './components/ProfileSetup';
import Settings from './components/Settings';
import Game from './components/Game';
import { useSupabaseAuth } from './utils/supabaseAuth';

const App = () => {
  const { isLoaded, isSignedIn } = useAuth();
  const { setSupabaseSession } = useSupabaseAuth();

  useEffect(() => {
    const checkProfileAndSetSession = async () => {
      if (isLoaded && isSignedIn) {
        // Set Supabase session
        const sessionSet = await setSupabaseSession();
        if (!sessionSet) {
          console.error('Failed to set Supabase session in App');
        }
      }
    };
    checkProfileAndSetSession();
  }, [isLoaded, isSignedIn, setSupabaseSession]);

  if (!isLoaded) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/feed" element={<Feed />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/profile-setup" element={<ProfileSetup />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/game" element={<Game />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  );
};

export default App;