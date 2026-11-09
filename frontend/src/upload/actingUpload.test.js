/**
 * Brief 28 D3: uploading for an artist (X-Acting-For). The header rides on every app call in
 * the batch (never on the storage PUT), acting-only refusals map to clear stops, and the song
 * form locks the artist's legal name and authorized uses.
 */
import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';

jest.mock('axios', () => ({ post: jest.fn(), put: jest.fn() }));
jest.mock('../components/ui/input', () => ({ Input: (p) => <input {...p} /> }));
jest.mock('../components/ui/label', () => ({ Label: ({ children, ...p }) => <label {...p}>{children}</label> }));
jest.mock('../components/ui/checkbox', () => ({
  Checkbox: ({ checked, onCheckedChange, ...p }) => (
    <input type="checkbox" checked={!!checked} onChange={(e) => onCheckedChange(e.target.checked)} {...p} />),
}));
jest.mock('../components/ui/select', () => ({
  Select: 'div', SelectContent: 'div', SelectItem: 'div', SelectTrigger: 'div', SelectValue: 'div',
}));
jest.mock('../components/ui/radio-group', () => ({ RadioGroup: 'div', RadioGroupItem: 'div' }));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('../agreement/agreementApi', () => ({ openAgreementPdf: jest.fn(), formatSignedDate: () => 'Oct 1, 2026' }));

import axios from 'axios';
import {
  classifyError, uploadOne, runBatch, authHeaders,
  ARTIST_AGREEMENT_DETAIL, ACTING_DENIED_DETAIL,
} from './useBatchUpload';
import SongForm, { emptySong } from './SongForm';
import { emptyRights } from '../sync/RightsSection';
import { EMPTY_DECLARATIONS, emptyLoop } from './declarations';

global.IS_REACT_ACT_ENVIRONMENT = true;
const err = (status, detail) => ({ response: { status, data: { detail } } });

describe('classifyError when acting', () => {
  test.each([
    [err(403, ARTIST_AGREEMENT_DETAIL), 'artist_agreement'],
    [err(403, ACTING_DENIED_DETAIL), 'acting_denied'],
    [err(403, 'This uploader is not authorized for AI training.'), 'fail'],
    [err(403, 'Only the artist can offer a song as exclusive.'), 'fail'],
    [err(429, "This artist's daily uploader limit is reached."), 'daily_limit'],
    [err(429, 'Too many uploads in progress for this artist.'), 'too_many'],
    // Unchanged for the artist's own uploads:
    [err(403, 'Forbidden'), 'approval'],
    [err(403, 'Sign the Artist Agreement before uploading.'), 'agreement'],
  ])('%#', (e, kind) => expect(classifyError(e)).toBe(kind));
});

test('authHeaders adds X-Acting-For only when acting', () => {
  expect(authHeaders('t', null)).toEqual({ Authorization: 'Bearer t' });
  expect(authHeaders('t', 'artist_1')).toEqual({ Authorization: 'Bearer t', 'X-Acting-For': 'artist_1' });
});

describe('uploadOne', () => {
  const loopSong = () => emptySong({
    form: { artist_name: 'A', track_name: 'T', genre: 'Pop' },
    file: { name: 't.wav', size: 10 }, consentSync: true, bpm: '100', musicalKey: 'C major',
    declarations: { ...EMPTY_DECLARATIONS, samples: 'royalty_free_loop',
      loops: [{ ...emptyLoop(), file: { name: 'l.pdf', type: 'application/pdf', size: 5 } }] },
    rights: { ...emptyRights(), owns_everything: true, self_legal_name: 'Jane Q Smith' },
  });
  beforeEach(() => {
    axios.post.mockReset().mockImplementation(async (url) => (
      /presign$/.test(url) ? { data: { presigned_url: 'https://r2/x', submission_id: 's1', content_type: 'audio/wav' } }
        : { data: {} }));
    axios.put.mockReset().mockResolvedValue({});
  });

  test('acting: every app call carries X-Acting-For; storage PUTs never do', async () => {
    await uploadOne(loopSong(), { getToken: async () => 't', api: 'A', onProgress: () => {}, actingFor: 'artist_1' });
    const urls = axios.post.mock.calls.map((c) => c[0]);
    expect(urls).toEqual(['A/upload/presign', 'A/upload/complete',
      'A/vault/tracks/s1/loops/0/license/presign', 'A/vault/tracks/s1/loops/0/license/complete']);
    axios.post.mock.calls.forEach((c) => expect(c[2].headers['X-Acting-For']).toBe('artist_1'));
    axios.put.mock.calls.forEach((c) => expect(c[2].headers['X-Acting-For']).toBeUndefined());
  });

  test('own upload: no X-Acting-For anywhere', async () => {
    await uploadOne(loopSong(), { getToken: async () => 't', api: 'A', onProgress: () => {} });
    axios.post.mock.calls.forEach((c) => expect(c[2].headers['X-Acting-For']).toBeUndefined());
  });
});

test('runBatch passes actingFor through and stops when the authorization is gone', async () => {
  const seen = [];
  const doUpload = jest.fn(async (song, deps) => { seen.push(deps.actingFor); throw err(403, ACTING_DENIED_DETAIL); });
  const states = {};
  const out = await runBatch([emptySong(), emptySong()], {
    getToken: async () => 't', patchSong: (k, p) => { states[k] = { ...states[k], ...p }; }, doUpload, actingFor: 'artist_1' });
  expect(out).toEqual({ stopReason: 'acting_denied' });
  expect(seen).toEqual(['artist_1']);          // stopped after the first song
  expect(Object.values(states).every((s) => s.status === 'queued')).toBe(true);
});

describe('SongForm when acting', () => {
  let c;
  const Harness = ({ initial, acting }) => {
    const [v, setV] = useState(initial);
    window.__song = v;
    return <SongForm value={v} index={0} onChange={(p) => setV((s) => ({ ...s, ...p }))} acting={acting}
      agreementStatus={{ legal_name: 'Uploader Own Name', signed: true, agreement: { signed_at: 'x' } }} getToken={async () => 't'} />;
  };
  const render = async (ui) => {
    c = document.createElement('div'); document.body.appendChild(c);
    await act(async () => { createRoot(c).render(ui); });
  };
  const ACTING = { artist_user_id: 'artist_1', artist_name: 'Jane Rivers', licensor_name: 'Jane Q Smith', uses: ['sync'] };

  test('locks the legal name to the artist licensor and clears unauthorized uses', async () => {
    const initial = emptySong({ consentAi: true,
      rights: { ...emptyRights(), self_legal_name: 'Typed By Uploader', legal_name_touched: true } });
    await render(<Harness initial={initial} acting={ACTING} />);
    expect(window.__song.rights.self_legal_name).toBe('Jane Q Smith');
    expect(window.__song.consentAi).toBe(false);
    const name = c.querySelector('[data-testid="upload-rights-legal-name"]');
    expect(name.readOnly).toBe(true);
    expect(c.querySelector('[data-testid="upload-rights-legal-name-locked"]').textContent)
      .toContain("Jane Rivers's Artist Agreement");
    expect(c.querySelector('[data-testid="upload-consent-ai-0"]').disabled).toBe(true);
    expect(c.querySelector('[data-testid="upload-consent-sync-0"]').disabled).toBe(false);
    expect(c.textContent).toContain("Jane Rivers hasn't authorized you to set AI training.");
    expect(c.textContent).not.toContain('View agreement');     // the artist's PDF is not the uploader's
    expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
  });

  test('own upload keeps the account name and both uses', async () => {
    await render(<Harness initial={emptySong({ consentAi: true })} acting={null} />);
    expect(window.__song.rights.self_legal_name).toBe('Uploader Own Name');
    expect(window.__song.consentAi).toBe(true);
    expect(c.querySelector('[data-testid="upload-rights-legal-name"]').readOnly).toBe(false);
  });
});
