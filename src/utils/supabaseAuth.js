import { useAuth } from '@clerk/clerk-react';
import { supabase } from './api';

export const useSupabaseAuth = () => {
  const { getToken } = useAuth();

  const setSupabaseSession = async () => {
    try {
      const token = await getToken({ template: 'supabase' });
      if (!token) {
        console.error('No Clerk JWT token received for supabase template');
        return false;
      }
      const { error } = await supabase.auth.setSession({ access_token: token });
      if (error) {
        console.error('Error setting Supabase session:', error.message);
        return false;
      }
      return true;
    } catch (err) {
      console.error('Failed to set Supabase session:', err.message || err);
      return false;
    }
  };

  return { setSupabaseSession };
};