import { accountFlags } from './account';

// user shape from Clerk: publicMetadata.{role,buyer}, unsafeMetadata.account_type
const U = ({ role, buyer, accountType } = {}) => ({
  publicMetadata: { ...(role ? { role } : {}), ...(buyer ? { buyer } : {}) },
  unsafeMetadata: accountType ? { account_type: accountType } : {},
});

describe('accountFlags (Brief 23 Part C)', () => {
  test('signed out shows nothing personal', () => {
    expect(accountFlags(null, false)).toMatchObject({
      isArtist: false, isAdmin: false, showVault: false, showAccount: false, isBuyerOnly: false,
    });
  });

  test('pending artist (no role) keeps My Vault, no account yet', () => {
    expect(accountFlags(U(), true)).toMatchObject({
      isArtist: true, showVault: true, hasBuyerAccess: false, showAccount: false, isBuyerOnly: false,
    });
  });

  test('approved artist keeps My Vault', () => {
    expect(accountFlags(U({ role: 'artist' }), true)).toMatchObject({ isArtist: true, showVault: true });
  });

  test('admin sees vault and account, never buyer-only', () => {
    expect(accountFlags(U({ role: 'admin' }), true)).toMatchObject({
      isAdmin: true, showVault: true, showAccount: true, isBuyerOnly: false,
    });
  });

  // Required: a pending artist who granted buyer access keeps My Vault and sees My account.
  test('pending artist with buyer:true keeps My Vault and gets My account', () => {
    expect(accountFlags(U({ buyer: true }), true)).toMatchObject({
      isArtist: true, showVault: true, hasBuyerAccess: true, showAccount: true, isBuyerOnly: false,
    });
  });

  // Required: a buyer sign-up later approved as an artist keeps My Vault.
  test('buyer sign-up later approved as artist keeps My Vault', () => {
    expect(accountFlags(U({ role: 'artist', accountType: 'buyer' }), true)).toMatchObject({
      isArtist: true, showVault: true, isBuyerOnly: false, showAccount: true,
    });
  });

  // Required: a pure buyer is buyer-only (the /vault redirect applies) and sees My account, not Vault.
  test('pure buyer is buyer-only, no Vault', () => {
    expect(accountFlags(U({ accountType: 'buyer' }), true)).toMatchObject({
      isArtist: false, showVault: false, isBuyerOnly: true, showAccount: true, hasBuyerAccess: true,
    });
  });
});
