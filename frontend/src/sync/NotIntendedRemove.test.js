/**
 * Brief 28 D5: the artist's "Didn't mean for this to be uploaded? Remove" (30 days).
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockNotIntended = jest.fn();
jest.mock('./api', () => ({ api: { notIntended: (...a) => mockNotIntended(...a) }, errorMessage: (e) => e.message }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import NotIntendedRemove from './NotIntendedRemove';

global.IS_REACT_ACT_ENVIRONMENT = true;
const DAY = 86400000;
const iso = (ms) => new Date(Date.now() + ms).toISOString();
const T = (over = {}) => ({ id: 't1', track_name: 'Midnight Ferry', upload_date: iso(-DAY),
  uploaded_by: { name: 'Sam Ortiz' }, not_intended_at: null, not_intended_until: iso(29 * DAY), ...over });

let c;
async function render(track, onUpdated = jest.fn()) {
  c = document.createElement('div'); document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<NotIntendedRemove track={track} getToken={async () => 't'} onUpdated={onUpdated} />); });
  return onUpdated;
}
const btn = (t) => [...c.querySelectorAll('button')].find((b) => b.textContent.trim() === t);
const click = async (el) => { await act(async () => { el.click(); }); };

beforeEach(() => { document.body.innerHTML = ''; mockNotIntended.mockReset(); });

test('within 30 days: offers Remove, asks first, explains existing licenses stay', async () => {
  mockNotIntended.mockResolvedValue({ removed: true, not_intended_at: iso(0), consent: { sync: false, ai_training: false } });
  const onUpdated = await render(T());
  expect(c.textContent).toContain("Didn't mean for this to be uploaded?");
  await click(btn('Remove'));
  expect(c.textContent).toContain('Remove "Midnight Ferry"?');
  expect(c.textContent).toContain('Sam Ortiz uploaded this');
  expect(c.textContent).toContain('Licenses already sold for this song stay in place');
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
  expect(mockNotIntended).not.toHaveBeenCalled();
  await click(c.querySelector('[data-testid="vault-not-intended-confirm-t1"]'));
  expect(mockNotIntended).toHaveBeenCalledWith(expect.any(Function), 't1');
  expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: 't1', removed: true }));
});

test('nothing for own uploads or after the window', async () => {
  await render(T({ uploaded_by: null }));
  expect(c.textContent).toBe('');
  await render(T({ not_intended_until: iso(-1000) }));
  expect(c.textContent).toBe('');
});

test('after removal: says so, no button', async () => {
  await render(T({ not_intended_at: '2026-10-30T12:00:00Z', not_intended_until: null }));
  expect(c.textContent).toContain('You removed this on Oct 30, 2026');
  expect(btn('Remove')).toBeUndefined();
});
