import React from 'react';
import { SignIn } from '@clerk/clerk-react';

const LoginPage = () => (
  <div className="min-h-screen bg-ink flex items-center justify-center px-4">
    <div className="w-full max-w-md">
      <div className="mb-8 text-center">
        <img src="/logo.png" alt="oVoxi" className="h-12 w-auto mx-auto mb-6" />
        <p className="text-slate-400 text-sm">Welcome back. Access your vault.</p>
      </div>
      <SignIn
        routing="path"
        path="/login"
        afterSignInUrl="/vault"
        appearance={{
          variables: {
            colorPrimary: '#9B59D4',
            colorBackground: '#111111',
            colorText: '#ffffff',
            colorTextSecondary: '#A3A3A3',
            colorInputBackground: '#1a1a1a',
            colorInputText: '#ffffff',
            borderRadius: '0.75rem',
          },
          elements: {
            socialButtonsBlockButton: 'text-white border-white/20',
            socialButtonsBlockButtonText: 'text-white font-medium',
          }
        }}
      />
    </div>
  </div>
);

export default LoginPage;
