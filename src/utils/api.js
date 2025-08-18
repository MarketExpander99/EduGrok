import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Placeholder for xAI API (post-funding)
export const xaiApi = async (endpoint, data) => {
  console.log('xAI API call placeholder', endpoint, data);
  return { mock: true };
};