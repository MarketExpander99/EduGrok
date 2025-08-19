import React from 'react';
import { createRoot } from 'react-dom/client';
import { ClerkProvider } from '@clerk/clerk-react';
import './styles/main.css';
import './styles/components.css';
import App from './App';
import reportWebVitals from './reportWebVitals';


const clerkPubKey = 'pk_test_ZGVzdGluZWQtc2F0eXItMzEuY2xlcmsuYWNjb3VudHMuZGV2JA';
//process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

const root = createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ClerkProvider publishableKey={clerkPubKey}>
      <App />
    </ClerkProvider>
  </React.StrictMode>
);

// Optional: Register service worker for offline
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then(registration => {
        console.log('SW registered: ', registration);
      })
      .catch(registrationError => {
        console.log('SW registration failed: ', registrationError);
      });
  });
}

reportWebVitals();