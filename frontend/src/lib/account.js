// Viewer flags derived from Clerk (Brief 23 Part C). The approved artist role wins over the
// sign-up label. publicMetadata.buyer is granted only through the buyer-access prompt, which
// only artists see, so it never cancels artist status: only the buyer sign-up label does.
export const accountFlags = (user, isSignedIn) => {
  const role = user?.publicMetadata?.role;
  const accountTypeBuyer = user?.unsafeMetadata?.account_type === 'buyer';
  const buyerFlag = user?.publicMetadata?.buyer === true;
  const isAdmin = role === 'admin';
  const isArtist = role === 'artist' || (!!isSignedIn && !accountTypeBuyer);
  const isBuyerOnly = accountTypeBuyer && role !== 'artist' && !isAdmin;
  const hasBuyerAccess = buyerFlag || accountTypeBuyer;
  const showVault = isAdmin || isArtist;
  const showAccount = isAdmin || hasBuyerAccess;
  return { role, accountTypeBuyer, buyerFlag, isAdmin, isArtist, isBuyerOnly, hasBuyerAccess, showVault, showAccount };
};

export default accountFlags;
