/**
 * Brief 25 Part E: the /pricing AI training section renders the four per-song
 * bands and three monthly plans, and a Contact sales button opens the quote form
 * prefilled and tagged kind "ai_training". react-dom + act in jsdom; deps mocked,
 * real constants.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockQuote = jest.fn();
jest.mock('./Modal', () => ({ children }) => <div>{children}</div>);
jest.mock('./QuoteForm', () => (props) => { mockQuote(props); return <div data-testid="quoteform" />; });
jest.mock('./SubscribeModal', () => () => null);
jest.mock('./PublicPageParts', () => ({ NotFound: () => <div>not found</div> }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));
jest.mock('./api', () => ({
  publicApi: { pricing: () => Promise.resolve({ visible: true, subscriptions_enabled: false, plans: [], singles: [] }) },
}));
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });
// Stable getToken reference so the pricing effect's deps don't change each render.
const mockGetToken = async () => 't';
jest.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ getToken: mockGetToken, isSignedIn: false, isLoaded: true }),
}));

import PricingPage from './PricingPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

const render = async () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  await act(async () => { createRoot(container).render(<PricingPage />); });
  return container;
};

const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); }); };

beforeEach(() => mockQuote.mockClear());

test('AI section shows only the three scope cards, each with Contact sales, and no prices', async () => {
  const c = await render();
  const ai = c.querySelector('[data-testid="ai-pricing"]');
  expect(ai).not.toBeNull();
  const text = ai.textContent;
  for (const scope of ['Personal', 'Research', 'Commercial']) expect(text).toContain(scope);
  const buttons = [...ai.querySelectorAll('button')].filter((b) => b.textContent.trim() === 'Contact sales');
  expect(buttons).toHaveLength(3);
  expect(text).not.toContain('$');
  expect(text).not.toContain('Per song, by order size');
  expect(text).not.toContain('Monthly plans');
});

test('a Contact sales button opens the quote form prefilled, tagged ai_training', async () => {
  const c = await render();
  const buttons = [...c.querySelectorAll('button')].filter((b) => b.textContent.trim() === 'Contact sales');
  expect(buttons.length).toBeGreaterThan(0);
  await click(buttons[0]);                       // first = Personal scope card
  const last = mockQuote.mock.calls.at(-1)[0];
  expect(last).toMatchObject({ kind: 'ai_training', message: 'AI training: Personal' });
});
