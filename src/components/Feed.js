import React, { useEffect, useState } from 'react';
import Post from './Post';
import LessonCard from './LessonCard';
import { supabase, useSupabaseAuth } from '../utils/api';
import { useUser } from '@clerk/clerk-react';

const grade4Lessons = [
  { title: 'Math: Fractions', content: 'Learn about adding fractions...', framework: 'Common Core' },
  // Add more static lessons for MVP
];

const Feed = () => {
  const { user } = useUser();
  const { setSupabaseSession } = useSupabaseAuth();
  const [posts, setPosts] = useState([]);
  const [lessons, setLessons] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      // Set Supabase session with Clerk JWT
      await setSupabaseSession();

      // Fetch posts
      const { data: postData } = await supabase.from('posts').select('*');
      const mappedPosts = postData?.map(post => ({
        ...post,
        username: post.username || post.user || 'Unknown User'
      })) || [];
      setPosts(mappedPosts);

      // Fetch user data if logged in
      if (user) {
        const { data: userData } = await supabase.from('users').select('framework, age').eq('id', user.id);
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
  }, [user, setSupabaseSession]);

  return (
    <div className="feed">
      {posts.map(post => <Post key={post.id} post={post} />)}
      {lessons.map((lesson, index) => <LessonCard key={index} lesson={lesson} />)}
    </div>
  );
};

export default Feed;