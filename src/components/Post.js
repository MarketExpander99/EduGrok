import React from 'react';
import { safetyFilter } from '../utils/safety';

const Post = ({ post }) => {
  const filteredContent = safetyFilter(post.content);

  const handleLike = () => {
    console.log('Like clicked for post:', post.id);
  };

  const handleRetweet = () => {
    console.log('Retweet clicked for post:', post.id);
  };

  const handleComment = () => {
    console.log('Comment clicked for post:', post.id);
  };

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
        <button onClick={handleLike}><i className="fas fa-heart"></i> {post.likes}</button>
        <button onClick={handleRetweet}><i className="fas fa-retweet"></i> {post.retweets}</button>
        <button onClick={handleComment}><i className="fas fa-comment"></i> {post.comments}</button>
        <a href={`https://x.com/intent/post?text=${encodeURIComponent(filteredContent)}`}><i className="fas fa-share"></i></a>
      </div>
    </div>
  );
};

export default Post;