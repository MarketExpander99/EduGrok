import React, { useEffect, useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';

const Profile = () => {
  const { user } = useUser();
  const [userData, setUserData] = useState({ score: 0, grade: 'A', lessons: 0, games: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      if (!user) return;
      setLoading(true);
      const { data, error } = await supabase.from('users').select('*').eq('id', user.id);
      if (error) console.error(error);
      else setUserData(data[0] || {});
      setLoading(false);
    };
    fetchUser();
  }, [user]);

  if (!user) return <p>Loading...</p>;
  if (loading) return <p>Loading profile...</p>;

  return (
    <div className="profile">
      <h2>Profile</h2>
      <p>Score: {userData.score}</p>
      <p>Grade: {userData.grade}</p>
      <p>Lessons Completed: {userData.lessons}</p>
      <p>Games Completed: {userData.games}</p>
      <a href="https://x.com/intent/post?text=I%20scored%20in%20EduGrok%27s%20Farm%20Math!%20Join%20me!%20%23EduGrok">
        <i className="fas fa-share"></i> Share to X
      </a>
    </div>
  );
};

export default Profile;