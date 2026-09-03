import React from 'react';
import ReactDOM from 'react-dom/client';
import '@/index.css';
import App from '@/App';
import { ClerkProvider } from '@clerk/clerk-react';

const PUBLISHABLE_KEY = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;
if (!PUBLISHABLE_KEY) {
  throw new Error('REACT_APP_CLERK_PUBLISHABLE_KEY is not set. Set it in Vercel and redeploy.');
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      signInUrl="/login"
      signUpUrl="/signup"
      signInForceRedirectUrl="/vault"
      signUpForceRedirectUrl="/vault"
      afterSignOutUrl="/"
    >
      <App />
    </ClerkProvider>
  </React.StrictMode>,
);
