import { createClient } from '@supabase/supabase-js';
import { useAuth } from '@clerk/clerk-react';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Supabase URL and Anon Key are required');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Hook to set Supabase session with Clerk JWT
export const useSupabaseAuth = () => {
  const { getToken } = useAuth();

  const setSupabaseSession = async () => {
    try {
      const token = await getToken({ template: 'supabase' });
      if (!token) {
        console.error('No Clerk JWT token received');
        return;
      }
      const { error } = await supabase.auth.setSession({ access_token: token });
      if (error) {
        console.error('Error setting Supabase session:', error.message);
      }
    } catch (err) {
      console.error('Failed to set Supabase session:', err);
    }
  };

  return { setSupabaseSession };
};