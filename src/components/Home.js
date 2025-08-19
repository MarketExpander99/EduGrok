import React from 'react';
import { useUser, SignedIn, SignedOut, SignInButton, SignUpButton } from '@clerk/clerk-react';
import { Link } from 'react-router-dom';

const Home = () => {
  const { user } = useUser();

  return (
    <div className="home">
      <h1>Welcome to EduGrok!</h1>
      <p>Safe, fun learning for kids worldwide.</p>
      <SignedOut>
        <SignInButton mode="modal">
          <button>Sign In</button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button>Sign Up</button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <p>Hello, {user?.firstName || 'User'}!</p>
        <Link to="/profile-setup">Complete Profile</Link>
        <Link to="/feed">Go to Feed</Link>
        <Link to="/profile">Profile</Link>
        <Link to="/settings">Settings</Link>
        <Link to="/game">Play Game</Link>
      </SignedIn>
    </div>
  );
};

export default Home;