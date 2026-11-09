/**
 * Brief 28 D6: admin Takedown dialog (Agreement 2.3(f)).
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockTakedown = jest.fn();
jest.mock('./api', () => ({ api: { adminTakedown: (...a) => mockTakedown(...a) }, errorMessage: (e) => e.message }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import TakedownDialog from './TakedownDialog';

global.IS_REACT_ACT_ENVIRONMENT = true;
const TRACK = { id: 't1', track_name: 'Midnight Ferry', artist_name: 'Jane Rivers', consent: { sync: true, ai_training: true } };

let c;
async function render(track = TRACK, onDone = jest.fn()) {
  c = document.createElement('div'); document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<TakedownDialog track={track} getToken={async () => 't'} onClose={jest.fn()} onDone={onDone} />); });
  return onDone;
}
const click = async (el) => { await act(async () => { el.click(); }); };
const pick = async (el, v) => {
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(el, v);
  await act(async () => { el.dispatchEvent(new Event('change', { bubbles: true })); });
};

beforeEach(() => { document.body.innerHTML = ''; mockTakedown.mockReset(); });

test('needs a reason; sends the chosen uses, reason and note', async () => {
  mockTakedown.mockResolvedValue({});
  const onDone = await render();
  const submit = c.querySelector('[data-testid="takedown-submit"]');
  expect(c.textContent).toContain('Takes effect right away for new licenses');
  expect(c.textContent).toContain('Licenses already sold stay in place');
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
  expect(submit.textContent).toBe('Take down 2 uses');
  expect(submit.disabled).toBe(true);                       // no reason yet
  await click(c.querySelector('input[data-use="ai_training"]'));
  await pick(c.querySelector('#td-reason'), 'upload_error');
  expect(submit.textContent).toBe('Take down 1 use');
  expect(submit.disabled).toBe(false);
  await click(submit);
  expect(mockTakedown).toHaveBeenCalledWith(expect.any(Function), 't1', { uses: ['sync'], reason: 'upload_error', note: null });
  expect(onDone).toHaveBeenCalled();
});

test('only uses that are on are offered', async () => {
  await render({ ...TRACK, consent: { sync: true, ai_training: false } });
  expect(c.querySelector('input[data-use="ai_training"]')).toBeNull();
  expect(c.querySelector('input[data-use="sync"]').checked).toBe(true);
});
