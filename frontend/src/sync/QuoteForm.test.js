/** Brief 23 D: the message prop prefills the quote form's details. */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

jest.mock('./api', () => ({ syncApi: { quote: jest.fn().mockResolvedValue({}) }, errorMessage: (e) => String(e) }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));

import QuoteForm from './QuoteForm';

global.IS_REACT_ACT_ENVIRONMENT = true;

test('message prop seeds the details textarea', async () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const msg = 'AI training license for "Night Drive" by Tyler';
  await act(async () => {
    createRoot(container).render(<QuoteForm kind="ai_training" message={msg} onDone={() => {}} />);
  });
  expect(container.querySelector('textarea').value).toBe(msg);
});
