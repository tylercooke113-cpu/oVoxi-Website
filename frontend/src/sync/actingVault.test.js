/**
 * Brief 28 D4: acting mode in the Vault track panel, and the acting header on api.* calls.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

jest.mock('../components/ui/input', () => ({ Input: (p) => <input {...p} /> }));
jest.mock('../components/ui/label', () => ({ Label: ({ children, ...p }) => <label {...p}>{children}</label> }));
jest.mock('../components/ui/checkbox', () => ({ Checkbox: (p) => <input type="checkbox" {...p} /> }));
jest.mock('../components/ui/select', () => ({
  Select: 'div', SelectContent: 'div', SelectItem: 'div', SelectTrigger: 'div', SelectValue: 'div',
}));
jest.mock('../components/ui/radio-group', () => ({ RadioGroup: 'div', RadioGroupItem: 'div' }));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

import { authed, actingGetToken } from './api';
import TrackSyncPanel from './TrackSyncPanel';

global.IS_REACT_ACT_ENVIRONMENT = true;

test('authed adds X-Acting-For only for an acting getToken', async () => {
  const gt = async () => 't';
  expect(await authed(gt)).toEqual({ headers: { Authorization: 'Bearer t' } });
  expect(await authed(actingGetToken(gt, 'artist_1')))
    .toEqual({ headers: { Authorization: 'Bearer t', 'X-Acting-For': 'artist_1' } });
});

describe('TrackSyncPanel', () => {
  let c;
  const track = (consent) => ({ id: 't1', consent, metadata: {}, loops: [], cosign: [], status: 'completed' });
  const render = async (props) => {
    c = document.createElement('div'); document.body.appendChild(c);
    await act(async () => { createRoot(c).render(
      <TrackSyncPanel getToken={async () => 't'} onUpdated={() => {}} status={{ exclusive_supported: true }} {...props} />); });
  };
  const sw = (label) => c.querySelector(`[role="switch"][aria-label="${label}"]`);

  test('artist: both switches usable, Exclusive shown', async () => {
    await render({ track: track({ sync: true, ai_training: false }) });
    expect(sw('Sync placements').disabled).toBe(false);
    expect(sw('AI training').disabled).toBe(false);
    expect(sw('Exclusive')).not.toBeNull();
  });

  test('acting: an "on" use cannot be turned off, unauthorized use locked, no Exclusive', async () => {
    await render({ track: track({ sync: true, ai_training: false }),
      acting: { artist_name: 'Jane Rivers', uses: ['sync'] } });
    expect(sw('Sync placements').disabled).toBe(true);          // on: only the artist turns it off
    expect(sw('AI training').disabled).toBe(true);              // not authorized
    expect(sw('Exclusive')).toBeNull();
    expect(c.textContent).toContain("Jane Rivers hasn't authorized you to set this use.");
    expect(c.textContent).toContain('Only Jane Rivers can turn a use off or take a song down.');
    expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
  });

  test('acting: an authorized "off" use can be turned on', async () => {
    await render({ track: track({ sync: true, ai_training: false }),
      acting: { artist_name: 'Jane Rivers', uses: ['sync', 'ai_training'] } });
    expect(sw('AI training').disabled).toBe(false);
  });
});
