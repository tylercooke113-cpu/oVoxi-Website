/**
 * Brief 20 B4 / B8 #6: verify the SubscriptionTab blocked_payment state renders the Option B
 * copy (decision 6) with no real card. Rendered with react-dom + act in jsdom; no new deps.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

// Stub the modal and the heavy data/router hooks so only SubscriptionTab's own markup renders.
jest.mock('../sync/SubscribeModal', () => () => null);
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
// react-router-dom v7 ships ESM-only; jest's CJS resolver can't load it, so mock virtually.
jest.mock('react-router-dom', () => ({ useSearchParams: () => [new URLSearchParams(), () => {}] }), { virtual: true });
jest.mock('../sync/checkout', () => ({
  useCheckoutConfig: () => ({ config: { plans: [] } }),
  fmtMoney: (c) => `$${(c / 100).toFixed(2)}`,
}));
const mockMe = jest.fn();
jest.mock('../sync/api', () => ({
  subscriptionsApi: { me: (...a) => mockMe(...a), portal: jest.fn(), resume: jest.fn() },
  errorMessage: (e) => String(e),
}));

import SubscriptionTab from './SubscriptionTab';

global.IS_REACT_ACT_ENVIRONMENT = true;

const BLOCKED = {
  state: 'blocked_payment',
  plan: 'pro',
  registered_count: 2,
  subscription: {
    plan_label: 'Pro', interval: 'month', price_cents: 4900,
    subscribed_since: '2026-06-01T00:00:00Z',
    grace_ends_at: '2026-10-20T00:00:00Z',   // present in the data; must NOT be shown in this state
  },
};

async function renderTab(data) {
  mockMe.mockResolvedValue(data);
  const container = document.createElement('div');
  document.body.appendChild(container);
  await act(async () => {
    createRoot(container).render(<SubscriptionTab getToken={async () => 't'} onViewProjects={() => {}} />);
  });
  return container;
}

test('blocked_payment renders Option B copy and hides grace dates', async () => {
  const text = (await renderTab(BLOCKED)).textContent;
  expect(text).toContain('Payment overdue');
  expect(text).toContain(
    'Your payment is overdue and downloads are paused. Update your card soon or your plan will be cancelled. Projects you already registered stay licensed.',
  );
  expect(text).toContain('Paused');
  expect(text).toContain('Update payment method');
  // No grace dates in this state.
  expect(text).not.toContain('Oct 20');
  expect(text).not.toContain('Available until');
});
