import { useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';
import { useSupabaseAuth } from '../utils/supabaseAuth';

const ProfileSetup = () => {
  const { user, isLoaded } = useUser();
  const { setSupabaseSession } = useSupabaseAuth();
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [framework, setFramework] = useState('Common Core');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!isLoaded || !user) {
      setError('User data not loaded');
      return;
    }

    const sessionSet = await setSupabaseSession();
    if (!sessionSet) {
      setError('Failed to authenticate with Supabase');
      return;
    }

    const userId = user.id;
    const { error: dbError } = await supabase
      .from('users')
      .upsert(
        { id: userId, name, age: parseInt(age), framework },
        { onConflict: ['id'] }
      );

    if (dbError) {
      console.error('Error saving profile:', dbError.message);
      setError('Failed to save profile');
    } else {
      setSuccess(true);
      setTimeout(() => {
        window.location.href = '/profile';
      }, 2000);
    }
  };

  if (!isLoaded) {
    return <div>Loading...</div>;
  }

  return (
    <div className="profile-setup">
      <h2>Complete Your Profile</h2>
      {error && <div className="error">{error}</div>}
      {success && <div className="success">Profile saved! Redirecting...</div>}
      <form onSubmit={handleSubmit}>
        <label>
          Name:
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Age:
          <input type="number" value={age} onChange={(e) => setAge(e.target.value)} required min="0" max="18" />
        </label>
        <label>
          Framework:
          <select value={framework} onChange={(e) => setFramework(e.target.value)}>
            <option value="Common Core">Common Core</option>
            <option value="IB">IB</option>
            <option value="National Curriculum">National Curriculum</option>
          </select>
        </label>
        <button type="submit">Save Profile</button>
      </form>
    </div>
  );
};

export default ProfileSetup;