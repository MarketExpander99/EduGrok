import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://fallback.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'fallback-anon-key';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

export function useSupabaseAuth() {
  const [user, setUser] = useState(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const getSession = async () => {
      try {
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw sessionError;
        setUser(session?.user || null);
        setIsLoaded(true);
      } catch (err) {
        console.error('Error getting session:', err.message);
        setError(err);
        setIsLoaded(true);
      }
    };

    getSession();

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
      setIsLoaded(true);
    });

    return () => {
      authListener.subscription.unsubscribe();
    };
  }, []);

  return { user, isLoaded, error };
}