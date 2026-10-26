// Brief 26: the four legal links appear in the footer on every page.
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a>,
}), { virtual: true });
jest.mock('lucide-react', () => ({ Mail: () => null }));

import { Footer } from './Footer';

global.IS_REACT_ACT_ENVIRONMENT = true;

test('footer links: Privacy Policy, Data Collection Policy, Do Not Sell, Terms of Service', async () => {
  const c = document.createElement('div');
  await act(async () => { createRoot(c).render(<Footer />); });
  const links = Object.fromEntries([...c.querySelectorAll('a')].map((a) => [a.textContent.trim(), a.getAttribute('href')]));
  expect(links['Privacy Policy']).toBe('/privacy');
  expect(links['Data Collection Policy']).toBe('/data-policy');
  expect(links['Do Not Sell or Share My Personal Information']).toBe('/privacy-choices');
  expect(links['Terms of Service']).toBe('/terms');
});
