/**
 * Brief 28 Part D1: the Vault "Authorized uploaders" tab. react-dom + act in jsdom; API mocked.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockList = jest.fn();
const mockPreview = jest.fn();
const mockCreate = jest.fn();
const mockRevoke = jest.fn();
jest.mock('./api', () => {
  const actual = jest.requireActual('./api');
  return { ...actual, uploadersApi: { list: (...a) => mockList(...a), preview: (...a) => mockPreview(...a),
    create: (...a) => mockCreate(...a), revoke: (...a) => mockRevoke(...a) } };
});
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));
jest.mock('../sync/api', () => ({ API: 'x', authed: async () => ({}), errorMessage: (e) => e?.message || 'err' }));
jest.mock('../agreement/AgreementDoc', () => () => <div data-testid="doc">doc</div>);

import AuthorizedUploadersTab, { SCOPE_COPY } from './AuthorizedUploadersTab';

global.IS_REACT_ACT_ENVIRONMENT = true;

const ROWS = [
  { id: 'a1', kind: 'person', uploader_name: 'Sam Ortiz', uploader_email: 'sam@x.com', uploader_role: 'Engineer',
    uses: ['sync', 'ai_training'], status: 'active', created_at: '2026-10-28T12:00:00Z' },
  { id: 'a2', kind: 'ovoxi', uploader_name: null, uploader_email: null, uploader_role: 'OVOXI',
    uses: ['sync'], status: 'active', created_at: '2026-10-27T12:00:00Z' },
  { id: 'a3', kind: 'person', uploader_name: 'Kai Bennett', uploader_email: 'kai@x.com', uploader_role: 'Producer',
    uses: ['sync'], status: 'revoked', created_at: '2026-10-02T12:00:00Z', revoked_at: '2026-10-20T12:00:00Z' },
];

let c;
async function render(props = {}) {
  c = document.createElement('div');
  document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<AuthorizedUploadersTab getToken={async () => 't'} legalName="Jane Rivers" {...props} />); });
}
const q = (sel) => c.querySelector(sel);
const btn = (text) => [...c.querySelectorAll('button')].find((b) => b.textContent.includes(text));
const click = async (el) => { await act(async () => { el.click(); }); };
const type = async (el, value) => {
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
  await act(async () => { el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); });
};

beforeEach(() => {
  document.body.innerHTML = '';
  [mockList, mockPreview, mockCreate, mockRevoke].forEach((m) => m.mockReset());
  mockList.mockResolvedValue(ROWS);
  mockPreview.mockResolvedValue({ blocks: [], text_sha256: 'a'.repeat(64) });
});

test('lists uploaders with uses, status and the scope copy', async () => {
  await render();
  expect(c.textContent).toContain(SCOPE_COPY);
  expect(q('[data-testid="uploader-a1"]').textContent).toContain('Sam Ortiz');
  expect(q('[data-testid="uploader-a1"]').textContent).toContain('AI training');
  expect(q('[data-testid="uploader-a2"]').textContent).toContain('OVOXI, Inc.');
  expect(q('[data-testid="uploader-a3"]').textContent).toContain('Revoked Oct 20, 2026');
  expect(q('[data-testid="uploader-a3"]').textContent).not.toContain('Revoke ');   // no action on ended rows
});

test('hides "Add OVOXI" when OVOXI is already active', async () => {
  await render();
  expect(btn('Add OVOXI as uploader')).toBeUndefined();
  mockList.mockResolvedValue([ROWS[0]]);
  await render();
  expect(btn('Add OVOXI as uploader')).toBeDefined();
});

test('empty state offers both ways to add', async () => {
  mockList.mockResolvedValue([]);
  await render();
  expect(c.textContent).toContain('No uploaders yet');
  expect(btn('+ Add uploader')).toBeDefined();
  expect(btn('Add OVOXI as uploader')).toBeDefined();
});

test('no copy contains an em or en dash', async () => {
  await render();
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
  await click(btn('+ Add uploader'));
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
});

test('add a person: validates, previews, signs with a matching name', async () => {
  mockCreate.mockResolvedValue({ ...ROWS[0], id: 'n1', status: 'awaiting_uploader', uploader_email: 'dee@n.co', uploader_name: 'Dee Lane' });
  await render();
  await click(btn('+ Add uploader'));
  await click(btn('Review and sign'));
  expect(c.textContent).toContain("Enter the uploader's name.");
  expect(mockPreview).not.toHaveBeenCalled();

  await type(q('#up-name'), '  Dee   Lane ');
  await type(q('#up-email'), 'dee@n.co');
  await type(q('#up-role'), 'Manager');
  await click(btn('Review and sign'));
  expect(c.textContent).toContain('Choose at least one use');

  await click(q('input[data-use="ai_training"]'));
  await click(btn('Review and sign'));
  expect(mockPreview).toHaveBeenCalledWith(expect.any(Function), {
    kind: 'person', uploader_name: 'Dee Lane', uploader_email: 'dee@n.co', uploader_role: 'Manager', uses: ['ai_training'] });
  expect(q('[data-testid="uploader-sign"]')).not.toBeNull();

  const signBtn = btn('Sign and send to Dee');
  expect(signBtn.disabled).toBe(true);
  await click(q('[data-testid="agree"]'));
  await type(q('#up-sig'), 'Someone Else');
  expect(signBtn.disabled).toBe(true);
  await type(q('#up-sig'), 'jane  rivers');
  expect(signBtn.disabled).toBe(false);
  await click(signBtn);
  expect(mockCreate).toHaveBeenCalledWith(expect.any(Function), expect.objectContaining({
    kind: 'person', uses: ['ai_training'], typed_signature: 'jane rivers', text_sha256: 'a'.repeat(64), consent_electronic: true }));
  expect(q('[data-testid="uploader-sent"]').textContent).toContain('Waiting for Dee to sign');
});

test('add OVOXI: no name, email or role; goes back to the list when signed', async () => {
  mockList.mockResolvedValue([]);
  mockCreate.mockResolvedValue({ ...ROWS[1] });
  await render();
  await click(btn('Add OVOXI as uploader'));
  expect(q('#up-name')).toBeNull();
  await click(q('input[data-use="sync"]'));
  await click(btn('Review and sign'));
  expect(mockPreview).toHaveBeenCalledWith(expect.any(Function), { kind: 'ovoxi', uses: ['sync'] });
  await click(q('[data-testid="agree"]'));
  await type(q('#up-sig'), 'Jane Rivers');
  await click(btn('Sign and add OVOXI'));
  expect(mockCreate).toHaveBeenCalled();
  expect(q('[data-testid="uploaders-list"]')).not.toBeNull();
});

test('a server refusal shows its message', async () => {
  mockPreview.mockRejectedValue(new Error('Sign the current Artist Agreement before adding an uploader.'));
  await render();
  await click(btn('+ Add uploader'));
  await type(q('#up-name'), 'Dee');
  await type(q('#up-email'), 'dee@n.co');
  await type(q('#up-role'), 'Manager');
  await click(q('input[data-use="sync"]'));
  await click(btn('Review and sign'));
  expect(c.textContent).toContain('Sign the current Artist Agreement before adding an uploader.');
});

test('revoke asks first, then calls the API', async () => {
  mockRevoke.mockResolvedValue({ status: 'revoked' });
  await render();
  const row = q('[data-testid="uploader-a1"]');
  await click([...row.querySelectorAll('button')].find((b) => b.textContent === 'Revoke'));
  expect(c.textContent).toContain('Revoke Sam Ortiz?');
  expect(mockRevoke).not.toHaveBeenCalled();
  await click(q('[data-testid="confirm-revoke"]'));
  expect(mockRevoke).toHaveBeenCalledWith(expect.any(Function), 'a1');
});
