import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

function Dashboard({ user }) {
  const [learnCoins, setLearnCoins] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProgress() {
      console.log('Fetching progress for user_id:', user.id); // Debug log
      const { data, error } = await supabase
        .from('user_progress')
        .select('points')
        .eq('user_id', user.id);
      if (error) {
        console.error('Error fetching progress:', error);
      } else {
        const totalCoins = data.reduce((sum, record) => sum + record.points, 0);
        setLearnCoins(totalCoins);
      }
      setLoading(false);
    }
    fetchProgress();
  }, [user.id]);

  if (loading) {
    return <div className="p-4 text-center" aria-live="polite">Loading...</div>;
  }

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">Your Dashboard</h1>
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold">Welcome, {user.age}-year-old Grade {user.grade} Student!</h2>
        <p className="mt-2">LearnCoins: <span className="font-bold text-blue-600">{learnCoins}</span></p>
        <p className="mt-2">Keep completing quizzes and games to earn more LearnCoins!</p>
      </div>
    </div>
  );
}

export default Dashboard;