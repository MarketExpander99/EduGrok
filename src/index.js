import { ClerkProvider } from '@clerk/clerk-react';
import { createRoot } from 'react-dom/client';
import App from './App';

// Debug: Log the env var to check if it's being read
console.log('Clerk Publishable Key:', process.env.REACT_APP_CLERK_PUBLISHABLE_KEY);

const clerkPubKey = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

const root = createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ClerkProvider publishableKey={clerkPubKey}>
      <App />
    </ClerkProvider>
  </React.StrictMode>
);