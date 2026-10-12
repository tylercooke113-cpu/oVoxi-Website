import React from 'react';
import { SignUp } from '@clerk/clerk-react';
import { useSearchParams } from 'react-router-dom';
import { safeNext } from '../lib/safeNext';

const SignUpPage = () => {
  const [params] = useSearchParams();
  const next = params.get('next');
  const redirect = safeNext(next);
  const isBuyer = params.get('as') === 'buyer';
  const carry = new URLSearchParams();
  if (isBuyer) carry.set('as', 'buyer');
  if (next) carry.set('next', next);
  const signInUrl = `/login${carry.toString() ? `?${carry.toString()}` : ''}`;
  return (
  <div className="min-h-screen bg-ink flex items-center justify-center px-4">
    <div className="w-full max-w-md">
      <div className="mb-8 text-center">
        <img src="/logo.png" alt="oVoxi" className="h-12 w-auto mx-auto mb-6" />
        {isBuyer ? (
          <>
            <h1 className="font-heading text-2xl font-semibold text-white">Create your buyer account</h1>
            <p className="mt-2 text-slate-400 text-sm">License tracks for your projects and manage your plan, certificates and downloads in one place.</p>
          </>
        ) : (
          <p className="text-slate-400 text-sm">Join the founding catalog. Get paid when your music licenses.</p>
        )}
      </div>
      <SignUp
        routing="path"
        path="/signup"
        forceRedirectUrl={redirect}
        signInUrl={signInUrl}
        {...(isBuyer ? { unsafeMetadata: { account_type: 'buyer' } } : {})}
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
};

export default SignUpPage;
