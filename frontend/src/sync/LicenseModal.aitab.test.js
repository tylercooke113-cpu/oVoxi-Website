/**
 * Brief 23 D: the License pop-up shows an AI training tab only for an AI-opted track, and
 * Contact sales opens the quote form prefilled. react-dom + act in jsdom; heavy deps mocked.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockQuote = jest.fn();
jest.mock('./Modal', () => ({ children }) => <div>{children}</div>);
jest.mock('./QuoteForm', () => (props) => { mockQuote(props); return <div data-testid="quoteform" />; });
jest.mock('./api', () => ({ errorMessage: (e) => String(e), subscriptionsApi: { me: jest.fn() }, accountApi: {} }));
jest.mock('./checkout', () => ({ checkoutApi: {}, fmtMoney: (c) => `$${(c / 100).toFixed(2)}` }));
jest.mock('./constants', () => ({ SUB_COPY: {} }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));

import LicenseModal from './LicenseModal';

global.IS_REACT_ACT_ENVIRONMENT = true;

const config = {
  tiers: [{ id: 'digital', label: 'Digital', description: 'Online use', price_cents: 1000 }],
  countries: [{ code: 'US', name: 'United States' }],
  subscriptions_enabled: false, terms_url: '/license-terms', stems_available: false,
};

const renderModal = async (track) => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  await act(async () => {
    createRoot(container).render(
      <LicenseModal track={track} config={config} onClose={() => {}} refreshConfig={() => {}}
        getToken={async () => 't'} isSignedIn={false} />);
  });
  return container;
};

const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); }); };

beforeEach(() => mockQuote.mockClear());

test('no AI tab when the track is not AI-opted', async () => {
  const c = await renderModal({ id: 't1', track_name: 'Night Drive', artist_display_name: 'Tyler', ai_training: false });
  expect(c.querySelector('[data-testid="license-tab-ai"]')).toBeNull();
});

test('AI tab shows for an AI-opted track; Contact sales opens the prefilled quote', async () => {
  const c = await renderModal({ id: 't1', track_name: 'Night Drive', artist_display_name: 'Tyler', ai_training: true });
  const aiTab = c.querySelector('[data-testid="license-tab-ai"]');
  expect(aiTab).not.toBeNull();
  await click(aiTab);
  expect(c.textContent).toContain('License this song to train AI models');
  await click(c.querySelector('[data-testid="ai-contact-sales"]'));
  expect(mockQuote).toHaveBeenCalledTimes(1);
  expect(mockQuote.mock.calls[0][0]).toMatchObject({
    kind: 'ai_training',
    message: 'AI training license for "Night Drive" by Tyler',
  });
});

// Brief 25b D3: tabs follow the listed uses; exclusive songs get the quote panel only.
test('AI-only listed track shows the AI panel with no tabs and no checkout', async () => {
  const c = await renderModal({ id: 't2', track_name: 'Ocean', artist_display_name: 'Kay', available_for: ['ai'] });
  expect(c.querySelector('[role="tablist"]')).toBeNull();
  expect(c.textContent).toContain('License this song to train AI models');
  expect(c.querySelector('[data-testid="license-continue"]')).toBeNull();
});

test('sync-only listed track shows no AI tab even if the artist opted into AI', async () => {
  const c = await renderModal({ id: 't3', track_name: 'Glow', artist_display_name: 'Kay', ai_training: true,
    available_for: ['sync'] });
  expect(c.querySelector('[data-testid="license-tab-ai"]')).toBeNull();
});

test('exclusive track: single panel, choices limited to listed uses, quote prefilled', async () => {
  const c = await renderModal({ id: 't4', track_name: 'Gold', artist_display_name: 'Kay', exclusive: true,
    available_for: ['sync', 'ai'] });
  expect(c.textContent).toContain('This song is offered as an exclusive license.');
  expect(c.querySelector('[data-testid="license-modal"]')).toBeNull();          // no tiers, no checkout
  expect(c.querySelector('[data-testid="exclusive-choice-both"]')).not.toBeNull();
  await click(c.querySelector('[data-testid="exclusive-choice-both"]'));
  await click(c.querySelector('[data-testid="exclusive-request-quote"]'));
  expect(mockQuote.mock.calls.at(-1)[0]).toMatchObject({ kind: 'exclusive', uses: ['sync', 'ai'] });
});

test('exclusive track listed for sync only offers only Sync', async () => {
  const c = await renderModal({ id: 't5', track_name: 'Gold', artist_display_name: 'Kay', exclusive: true,
    available_for: ['sync'] });
  expect(c.querySelector('[data-testid="exclusive-choice-sync"]')).not.toBeNull();
  expect(c.querySelector('[data-testid="exclusive-choice-ai"]')).toBeNull();
  expect(c.querySelector('[data-testid="exclusive-choice-both"]')).toBeNull();
});
