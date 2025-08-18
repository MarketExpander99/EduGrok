import React, { useEffect } from 'react';
import { SignedIn, SignedOut, SignIn, SignUp } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const navigate = useNavigate();

  return (
    <div className="login">
      <SignedIn>
        <p>Logged in! Redirecting...</p>
        {useEffect(() => { navigate('/feed'); }, [])}
      </SignedIn>
      <SignedOut>
        <SignIn afterSignInUrl="/profile-setup" />
        <SignUp afterSignUpUrl="/profile-setup" />
      </SignedOut>
    </div>
  );
};

export default Login;