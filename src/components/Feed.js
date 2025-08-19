import React, { useEffect, useState } from 'react';
import Post from './Post';
import LessonCard from './LessonCard';
import { supabase } from '../utils/api';
import { useSupabaseAuth } from '../utils/supabaseAuth';
import { useUser, useAuth } from '@clerk/clerk-react';

const grade4Lessons = [
  { title: 'Math: Fractions', content: 'Learn about adding fractions...', framework: 'Common Core' },
  // Add more static lessons for MVP
];

const Feed = () => {
  const { user } = useUser();
  const { isSignedIn, isLoaded } = useAuth();
  const { setSupabaseSession } = useSupabaseAuth();
  const [posts, setPosts] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setError(null);
      if (!isLoaded) {
        setError('Loading authentication...');
        return;
      }
      if (!isSignedIn) {
        setError('Please sign in to view the feed');
        return;
      }

      // Wait for Clerk session to stabilize
      await new Promise(resolve => setTimeout(resolve, 500));

      // Set Supabase session
      const sessionSet = await setSupabaseSession();
      if (!sessionSet) {
        setError('Failed to authenticate with Supabase');
        return;
      }

      // Fetch posts
      const { data: postData, error: postError } = await supabase.from('posts').select('*');
      if (postError) {
        console.error('Error fetching posts:', postError.message);
        setError('Failed to load posts');
        return;
      }
      const mappedPosts = postData?.map(post => ({
        ...post,
        username: post.username || post.user || 'Unknown User'
      })) || [];
      setPosts(mappedPosts);

      // Fetch user data if logged in
      if (user) {
        const { data: userData, error: userError } = await supabase.from('users').select('framework, age').eq('id', user.id);
        if (userError) {
          console.error('Error fetching user data:', userError.message);
          setError('Failed to load user data');
          return;
        }
        if (userData?.length > 0) {
          const { age, framework } = userData[0];
          if (age >= 9 && age <= 10) {
            const filteredLessons = grade4Lessons.filter(l => l.framework === framework);
            setLessons(filteredLessons);
          }
        }
      }
    };
    fetchData();
  }, [user, isSignedIn, isLoaded, setSupabaseSession]);

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="feed">
      {posts.map(post => <Post key={post.id} post={post} />)}
      {lessons.map((lesson, index) => <LessonCard key={index} lesson={lesson} />)}
    </div>
  );
};

export default Feed;