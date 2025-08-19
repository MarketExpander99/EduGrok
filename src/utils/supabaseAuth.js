import { useAuth } from '@clerk/clerk-react';
import { supabase } from './api';

export const useSupabaseAuth = () => {
  const { getToken, isSignedIn, isLoaded } = useAuth();

  const setSupabaseSession = async () => {
    if (!isLoaded || !isSignedIn) {
      console.error('Clerk session not loaded or not signed in');
      return false;
    }

    try {
      // Wait for session to stabilize
      await new Promise(resolve => setTimeout(resolve, 1500)); // Increased to 1.5s

      // Retry up to 3 times with delay
      let attempts = 0;
      const maxAttempts = 3;
      while (attempts < maxAttempts) {
        const token = await getToken({ template: 'supabase' });
        if (token) {
          const { error } = await supabase.auth.setSession({ access_token: token });
          if (error) {
            console.error('Error setting Supabase session:', error.message);
            return false;
          }
          return true;
        }
        console.warn(`No Clerk JWT token received (attempt ${attempts + 1}/${maxAttempts})`);
        attempts++;
        await new Promise(resolve => setTimeout(resolve, 1000)); // 1s delay between retries
      }
      console.error('Failed to get Clerk JWT token after retries');
      return false;
    } catch (err) {
      console.error('Failed to set Supabase session:', err.message || err);
      return false;
    }
  };

  return { setSupabaseSession };
};