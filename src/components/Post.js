import React from 'react';
import { safetyFilter } from '../utils/safety';

const Post = ({ post }) => {
  const filteredContent = safetyFilter(post.content);

  return (
    <div className="post">
      <div className="post-header">
        <img src="https://via.placeholder.com/40" alt={post.handle} />
        <div>
          <strong>{post.user}</strong>
          <span>{post.handle} · {post.date}</span>
        </div>
      </div>
      <p>{filteredContent}</p>
      <div className="post-actions">
        <a href="#"><i className="fas fa-heart"></i> {post.likes}</a>
        <a href="#"><i className="fas fa-retweet"></i> {post.retweets}</a>
        <a href="#"><i className="fas fa-comment"></i> {post.comments}</a>
        <a href={`https://x.com/intent/post?text=${encodeURIComponent(filteredContent)}`}><i className="fas fa-share"></i></a>
      </div>
    </div>
  );
};

export default Post;