import React from 'react';
import { Link } from 'react-router-dom';

const Sidebar = () => {
  return (
    <div className="sidebar">
      <Link to="/"><i className="fas fa-home"></i> Home</Link>
      <Link to="/profile"><i className="fas fa-user"></i> Profile</Link>
      <Link to="/feed"><i className="fas fa-post"></i> Feed</Link>
      <Link to="/"><i className="fas fa-robot"></i> Grok</Link>
    </div>
  );
};

export default Sidebar;