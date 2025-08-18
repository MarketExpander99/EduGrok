import React from 'react';
import { Link } from 'react-router-dom';

const Home = () => {
  return (
    <div className="home">
      <h1>Welcome to EduGrok!</h1>
      <p>Learn with fun, safe, and interactive homeschooling tools powered by xAI.</p>
      <Link to="/login"><button className="cta-button">Sign Up</button></Link>
      <Link to="/feed"><button className="cta-button">Explore Feed</button></Link>
    </div>
  );
};

export default Home;