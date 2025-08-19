import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';
import { useSupabaseAuth } from '../utils/supabaseAuth';

const PrivateRoute = ({ children }) => {
  const { user, isSignedIn, isLoaded } = useUser();
  const { setSupabaseSession } = useSupabaseAuth();
  const [hasProfile, setHasProfile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkProfile = async () => {
      if (!isLoaded || !isSignedIn || !user) return;

      await setSupabaseSession();

      const { data, error } = await supabase.from('users').select('id').eq('id', user.id);
      if (error) {
        console.error('Error checking profile:', error.message);
        setError('Failed to check profile');
        return;
      }
      setHasProfile(data?.length > 0);
    };
    checkProfile();
  }, [user, isLoaded, isSignedIn, setSupabaseSession]);

  if (error) {
    return '<div>Error: {error}</div>';
  }

  if (!isSignedIn) {
    return '<Navigate to="/" />';
  }

  if (hasProfile === null) {
    return '<div>Loading...</div>';
  }

  if (!hasProfile) {
    return '<Navigate to="/profile-setup" />';
  }

  return children;
};

export default PrivateRoute;