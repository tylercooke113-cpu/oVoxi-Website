/**
 * Brief 27 Part D: the Vault Wallet tab shows the four numbers, the lines, statements and
 * the payout setup state. react-dom + act in jsdom; the API is mocked.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockMe = jest.fn();
const mockStatus = jest.fn();
const mockConnect = jest.fn();
const mockOverview = jest.fn();
jest.mock('./api', () => {
  const actual = jest.requireActual('./api');
  return { ...actual, walletApi: { me: (...a) => mockMe(...a), status: (...a) => mockStatus(...a),
    connect: (...a) => mockConnect(...a), dashboard: jest.fn(), statement: jest.fn() },
    adminWalletApi: { overview: (...a) => mockOverview(...a), exclusives: async () => [] } };
});
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), message: jest.fn() } }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));
jest.mock('../sync/api', () => ({ API: 'x', authed: async () => ({}), errorMessage: (e) => String(e) }));

import WalletTab from './WalletTab';
import AdminPayouts from './AdminPayouts';
import { money } from './api';

global.IS_REACT_ACT_ENVIRONMENT = true;

const DATA = {
  summary: { earned_this_month_cents: 1597, available_cents: 3186, held_cents: 0, paid_cents: 12000, pending_cents: 1597 },
  entries: [
    { id: 'a', date: '2026-11-05T00:00:00Z', track_title: 'Night Drive', kind: 'Sync license', field: 'sync', share_bp: 5000, amount_cents: 1597, status: 'accrued', test_mode: false },
    { id: 'b', date: '2026-11-06T00:00:00Z', track_title: 'Night Drive', kind: 'Refund', field: 'sync', share_bp: 5000, amount_cents: -400, status: 'accrued', test_mode: false },
  ],
  statements: [{ period: '2026-10', period_label: 'October 2026', revenue_share_cents: 3186 }],
  connect: { connected: false }, test_mode: false, minimum_cents: 2500,
};

async function render(ui) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  await act(async () => { createRoot(c).render(ui); });
  return c;
}

beforeEach(() => {
  mockMe.mockReset().mockResolvedValue(DATA);
  mockStatus.mockReset().mockResolvedValue({ connected: false, suggested_country: 'US', countries: [{ code: 'US', name: 'United States' }] });
});

test('money formats cents', () => {
  expect(money(318600)).toBe('$3,186.00');
  expect(money(-400)).toBe('-$4.00');
  expect(money(0)).toBe('$0.00');
});

test('shows the four numbers, the lines and statements', async () => {
  const c = await render(<WalletTab getToken={async () => 't'} />);
  expect(c.querySelector('[data-testid="wallet-earned"]').textContent).toContain('$15.97');
  expect(c.querySelector('[data-testid="wallet-available"]').textContent).toContain('$31.86');
  expect(c.querySelector('[data-testid="wallet-paid"]').textContent).toContain('$120.00');
  const rows = c.querySelectorAll('[data-testid="wallet-entries"] tbody tr');
  expect(rows).toHaveLength(2);
  expect(rows[1].textContent).toContain('-$4.00');
  expect(c.querySelector('[data-testid="wallet-statements"]').textContent).toContain('October 2026');
  expect(c.textContent).toContain('Balances under $25.00 roll over to the next month.');
});

test('payout setup: country prefilled from the agreement, then Connect', async () => {
  const c = await render(<WalletTab getToken={async () => 't'} />);
  expect(c.querySelector('[data-testid="wallet-country"]').value).toBe('US');
  expect(c.querySelector('[data-testid="wallet-connect-button"]').textContent).toBe('Connect your bank account');
});

test('verified payee sees payouts on', async () => {
  mockMe.mockResolvedValue({ ...DATA, connect: { connected: true, payouts_enabled: true } });
  const c = await render(<WalletTab getToken={async () => 't'} />);
  expect(c.querySelector('[data-testid="wallet-verified"]').textContent).toContain('Verified, payouts on');
});

test('unsupported country shows the message', async () => {
  mockMe.mockResolvedValue({ ...DATA, connect: { connected: false, unsupported: true,
    message: 'Payouts are not available in your country yet. Email tyler@ovoxi.net.' } });
  const c = await render(<WalletTab getToken={async () => 't'} />);
  expect(c.querySelector('[data-testid="wallet-unsupported"]').textContent).toContain('not available in your country yet');
});

test('admin payouts: deadline banner, groups, and pay locked until the month is closed', async () => {
  mockOverview.mockResolvedValue({
    period: '2026-10', period_label: 'October 2026', livemode: false, payment_due: '2026-12-15', december: false,
    closed: null, payouts: [], holds: [], minimum_cents: 2500,
    preview: { pay: [{ payee_key: 'user_a', email: null, amount_cents: 3186 }], below_minimum: [{ payee_key: 'user_b', amount_cents: 900 }],
      not_verified: [], no_account: [], unsupported: [], negative: [], total_to_pay_cents: 3186 },
  });
  const c = await render(<AdminPayouts getToken={async () => 't'} />);
  expect(c.querySelector('[data-testid="payout-deadline"]').textContent).toContain('Payments for October 2026 are due by December 15, 2026.');
  const btn = c.querySelector('[data-testid="payout-approve"]');
  expect(btn.textContent).toBe('Approve and pay $31.86');
  expect(btn.disabled).toBe(true);
  expect(c.textContent).toContain('Below $25 (rolls over) (1)');
});
