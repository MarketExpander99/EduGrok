import React, { useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';
import { Link, useNavigate } from 'react-router-dom';

const frameworks = ['Common Core', 'IB', 'Cambridge', 'National Curriculum']; // Example frameworks

const ProfileSetup = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [email, setEmail] = useState('');
  const [framework, setFramework] = useState(frameworks[0]);
  const [termsAccepted, setTermsAccepted] = useState(false);

  if (!user) return <p>Loading...</p>;

  const handleSubmit = async () => {
    if (termsAccepted) {
      await supabase.from('users').insert([{ 
        id: user.id, 
        name, 
        age, 
        parent_email: email,
        framework 
      }]);
      navigate('/feed');
    }
  };

  return (
    <div className="profile-setup">
      <h2>Set Up Your Profile</h2>
      <input type="text" placeholder="Name" onChange={e => setName(e.target.value)} />
      <input type="number" placeholder="Age" onChange={e => setAge(e.target.value)} />
      <input type="email" placeholder="Parent Email" onChange={e => setEmail(e.target.value)} />
      <select value={framework} onChange={e => setFramework(e.target.value)}>
        {frameworks.map(f => <option key={f} value={f}>{f}</option>)}
      </select>
      <label>
        <input type="checkbox" onChange={e => setTermsAccepted(e.target.checked)} />
        I accept the <Link to="/terms">Terms & Conditions</Link>
      </label>
      <button onClick={handleSubmit}>Save</button>
    </div>
  );
};

export default ProfileSetup;