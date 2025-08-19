import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useUser, useAuth } from '@clerk/clerk-react';
import Home from './components/Home';
import Feed from './components/Feed';
import Profile from './components/Profile';
import ProfileSetup from './components/ProfileSetup';
import Settings from './components/Settings';
import Game from './components/Game';
import PrivateRoute from './components/PrivateRoute';
import { supabase } from './utils/api';
import { useSupabaseAuth } from './utils/supabaseAuth';

const App = () => {
  const { user, isLoaded } = useUser();
  const { isSignedIn } = useAuth();
  const { setSupabaseSession } = useSupabaseAuth();

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      setSupabaseSession();
    }
  }, [isLoaded, isSignedIn, setSupabaseSession]);

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/profile-setup" element={<ProfileSetup />} />
        <Route path="/feed" element={<PrivateRoute><Feed /></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
        <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
        <Route path="/game" element={<PrivateRoute><Game /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  );
};

export default App;