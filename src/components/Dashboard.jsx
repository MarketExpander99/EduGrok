import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

// Enhanced debug logs
console.log('Dashboard.jsx - Checking environment variables:');
try {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'undefined';
  console.log('VITE_SUPABASE_URL:', supabaseUrl);
  const url = new URL(supabaseUrl);
  console.log('Validated URL:', url.href);
  const supabase = createClient(supabaseUrl, import.meta.env.VITE_SUPABASE_ANON_KEY || 'fallback-anon-key');
  console.log('Supabase client initialized with URL:', supabaseUrl);
} catch (e) {
  console.error('Invalid URL in Dashboard.jsx:', e, 'Value:', import.meta.env.VITE_SUPABASE_URL);
}

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://zahrotkjbhfegvwsevjy.supabase.co',
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InphaHJvdGtqYmhmZWd2d3Nldmp5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU1MzcwNDksImV4cCI6MjA3MTExMzA0OX0.PJHE_2uvVuixA1velpE-KPmD4o2W-UENiegcZl1wFI8'
);

function Dashboard({ user }) {
  const [learnCoins, setLearnCoins] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProgress() {
      console.log('Fetching progress for user_id:', user.id, 'with URL:', supabaseUrl);
      const { data, error } = await supabase
        .from('user_progress')
        .select('points')
        .eq('user_id', user.id);
      if (error) {
        console.error('Error fetching progress:', error, 'Response:', data);
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