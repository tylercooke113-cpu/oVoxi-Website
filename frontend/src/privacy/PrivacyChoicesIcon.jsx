import React from 'react';

// The opt-out icon shown next to "Your Privacy Choices" (California 11 CCR 7015): a blue
// toggle with a check and a cross, sized to sit beside footer text.
export default function PrivacyChoicesIcon({ className = 'h-[14px] w-[30px]' }) {
  return (
    <svg viewBox="0 0 30 14" className={className} aria-hidden="true" focusable="false">
      <rect x="0.5" y="0.5" width="29" height="13" rx="6.5" fill="#fff" stroke="#0066FF" />
      <path d="M15 0.5h8a6.5 6.5 0 0 1 0 13h-8z" fill="#0066FF" />
      <path d="M5.2 7.1l2 2 3.8-4.2" fill="none" stroke="#0066FF" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19.4 4.6l4.8 4.8M24.2 4.6l-4.8 4.8" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
