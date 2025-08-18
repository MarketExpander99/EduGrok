import React, { useEffect, useState } from 'react';
import Post from './Post';
import LessonCard from './LessonCard';
import { supabase } from '../utils/api';
import { useUser } from '@clerk/clerk-react';

const grade4Lessons = [
  { title: 'Math: Fractions', content: 'Learn about adding fractions...', framework: 'Common Core' },
  // Add more static lessons for MVP
];

const Feed = () => {
  const { user } = useUser();
  const [posts, setPosts] = useState([]);
  const [lessons, setLessons] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const { data: postData } = await supabase.from('posts').select('*');
      setPosts(postData || []);

      if (user) {
        const { data: userData } = await supabase.from('users').select('framework, age').eq('id', user.id);
        if (userData[0] && userData[0].age >= 9 && userData[0].age <= 10) { // Assuming grade 4 is age 9-10
          const framework = userData[0].framework;
          const filteredLessons = grade4Lessons.filter(l => l.framework === framework);
          setLessons(filteredLessons);
        }
      }
    };
    fetchData();
  }, [user]);

  return (
    <div className="feed">
      {posts.map(post => <Post key={post.id} post={post} />)}
      {lessons.map((lesson, index) => <LessonCard key={index} lesson={lesson} />)}
    </div>
  );
};

export default Feed;