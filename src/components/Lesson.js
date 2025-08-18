import React, { useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';

const Lesson = () => {
  const { user } = useUser();
  const [answer, setAnswer] = useState('');
  const [submitted, setSubmitted] = useState(false);

  if (!user) return <p>Loading...</p>;

  const handleSubmit = async () => {
    setSubmitted(true);
    // Sync to Supabase
    await supabase.from('lessons').insert([{ user_id: user.id, answer }]);
    localStorage.setItem('lessonAnswer', answer);
  };

  return (
    <div className="lesson">
      <h2>Farm Addition Lesson</h2>
      <p>How many cows? 2 + 3 = ?</p>
      <label>
        <input type="radio" value="5" onChange={e => setAnswer(e.target.value)} /> 5
      </label>
      <label>
        <input type="radio" value="6" onChange={e => setAnswer(e.target.value)} /> 6
      </label>
      <button onClick={handleSubmit}>Submit</button>
      {submitted && <p>Earn 10 points!</p>}
    </div>
  );
};

export default Lesson;