import React, { useEffect, useState } from 'react';
import { useUser, useAuth } from '@clerk/clerk-react';
import { supabase } from '../utils/api';
import { useSupabaseAuth } from '../utils/supabaseAuth';

const Profile = () => {
  const { user } = useUser();
  const { isSignedIn } = useAuth();
  const { setSupabaseSession } = useSupabaseAuth();
  const [userData, setUserData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchUserData = async () => {
      if (!isSignedIn || !user) {
        setError('Please sign in to view your profile');
        return;
      }

      setError(null);
      // Set Supabase session
      const sessionSet = await setSupabaseSession();
      if (!sessionSet) {
        setError('Failed to authenticate with Supabase');
        return;
      }

      const { data, error } = await supabase.from('users').select('*').eq('id', user.id);
      if (error) {
        console.error('Error fetching user data:', error.message);
        setError('Failed to load profile: ' + error.message);
        return;
      }
      if (data?.length > 0) {
        setUserData(data[0]);
      } else {
        setError('No profile data found');
      }
    };
    fetchUserData();
  }, [user, isSignedIn, setSupabaseSession]);

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  if (!userData) {
    return <div>Loading profile...</div>;
  }

  return (
    <div className="profile">
      <h2>{userData.name || user.firstName}'s Profile</h2>
      <p>Age: {userData.age || 'Not set'}</p>
      <p>Grade: {userData.grade || 'Not set'}</p>
      <p>Framework: {userData.framework || 'Not set'}</p>
      <p>Score: {userData.score || 0}</p>
      <p>Lessons Completed: {userData.lessons || 0}</p>
      <p>Games Played: {userData.games || 0}</p>
    </div>
  );
};

export default Profile;