import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { useUser, useAuth } from '@clerk/clerk-react';
import { publicApi } from '../sync/api';
import { accountFlags } from '../lib/account';
import { readFlag, writeFlag } from '../lib/siteFlags';
import BuyerAccessModal from './BuyerAccessModal';

const Logo = () => (
  <Link to="/" data-testid="logo-link" className="flex items-center group">
    <img
      src="/logo.png"
      alt="OVOXI"
      className="h-10 w-auto transition-opacity group-hover:opacity-80"
    />
  </Link>
);

export const Header = () => {
  const { isSignedIn, user } = useUser();
  const { getToken, isSignedIn: authedIn, isLoaded } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [buyerPrompt, setBuyerPrompt] = useState(false);
  // Until Clerk loads, assume a signed-out visit (the safe default).
  const [pricingVisible, setPricingVisible] = useState(() => readFlag('pricing_visible', false));
  const [catalogVisible, setCatalogVisible] = useState(() => readFlag('library_visible', false));

  // B5 / Brief 23 C1: the Pricing and catalog links follow /api/sync/pricing. `visible` gates
  // Pricing; `library_visible` (SYNC_LIBRARY_ENABLED or admin) gates the catalog links. Fetch
  // once per load and again on sign-in or sign-out. Flags are cached per auth state, so an
  // admin's flags never show after logout.
  useEffect(() => {
    if (!isLoaded) return undefined;
    const signedIn = !!authedIn;
    setPricingVisible(readFlag('pricing_visible', signedIn));
    setCatalogVisible(readFlag('library_visible', signedIn));
    let alive = true;
    publicApi.pricing(getToken, authedIn)
      .then((d) => {
        if (!alive) return;
        setPricingVisible(!!d.visible);
        setCatalogVisible(!!d.library_visible);
        writeFlag('pricing_visible', signedIn, !!d.visible);
        writeFlag('library_visible', signedIn, !!d.library_visible);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [getToken, authedIn, isLoaded]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const closeMenu = () => setOpen(false);
  const openPrompt = () => { setOpen(false); setBuyerPrompt(true); };

  const f = accountFlags(user, isSignedIn);
  const showVault = f.showVault;
  const showAccount = f.showAccount;
  // Pricing: signed-out visitors and buyers/admins see it (when visible); artists without
  // buyer access do not. Contact stays available to everyone.
  const showPricing = pricingVisible && (!isSignedIn || f.isAdmin || f.hasBuyerAccess);
  // Catalog link: a direct link for buyers/admins/artists-with-access; a "Browse" button that
  // opens the buyer-access prompt for an artist without access. Both gated by catalogVisible.
  const browsePrompt = catalogVisible && isSignedIn && f.isArtist && !f.hasBuyerAccess && !f.isAdmin;
  const catalogLink = catalogVisible && isSignedIn && !browsePrompt;
  const browseSignedOut = catalogVisible && !isSignedIn;

  const linkCls = 'text-sm font-medium text-slate-300 hover-text-gradient transition-colors';
  const gradientCls = 'rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)]';

  // One render of the nav items, reused for desktop (row) and mobile (column).
  const items = (mobile) => {
    const cls = mobile ? 'text-base font-medium text-slate-300 hover-text-gradient' : linkCls;
    const click = mobile ? closeMenu : undefined;
    return (
      <>
        {showVault && (
          <Link to="/vault" onClick={click} data-testid="nav-vault" className={cls}>My Vault</Link>
        )}
        {browseSignedOut && (
          <Link to="/catalog" onClick={click} data-testid="nav-browse"
            className={mobile ? `${gradientCls} text-center` : gradientCls}>Browse OVOXI Catalog</Link>
        )}
        {browsePrompt && (
          <button type="button" onClick={openPrompt} data-testid="nav-browse" className={`${cls} text-left`}>
            Browse OVOXI Catalog
          </button>
        )}
        {catalogLink && (
          <Link to="/catalog" onClick={click} data-testid="nav-catalog" className={cls}>OVOXI Catalog</Link>
        )}
        {showPricing && (
          <Link to="/pricing" onClick={click} data-testid="nav-pricing" className={cls}>Pricing</Link>
        )}
        {showAccount && (
          <Link to="/account" onClick={click} data-testid="nav-account" className={cls}>My account</Link>
        )}
        <Link to="/contact" onClick={click} data-testid="nav-contact" className={cls}>Contact</Link>
        {!isSignedIn && (
          <>
            <Link to="/signup" onClick={click} data-testid="header-artist-cta" className={cls}>Artists</Link>
            <Link to={catalogVisible ? '/catalog' : '/contact?interest=ai_company'} onClick={click}
              data-testid="header-partnership-cta"
              className={mobile ? `${gradientCls} text-center` : gradientCls}>Discuss Licensing</Link>
          </>
        )}
      </>
    );
  };

  return (
    <header
      data-testid="site-header"
      className={`fixed top-0 inset-x-0 z-50 transition-colors duration-300 ${
        scrolled ? 'bg-black/80 backdrop-blur-xl border-b border-white/10' : 'bg-transparent'
      }`}
    >
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Logo />

          <div className="hidden md:flex items-center gap-5">
            {items(false)}
          </div>

          <button
            data-testid="mobile-menu-toggle"
            className="md:hidden text-white"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {open ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {open && (
        <div data-testid="mobile-menu" className="md:hidden bg-black/95 backdrop-blur-xl border-b border-white/10">
          <div className="px-6 py-4 flex flex-col gap-4">
            {items(true)}
          </div>
        </div>
      )}

      {buyerPrompt && (
        <BuyerAccessModal
          onClose={() => setBuyerPrompt(false)}
          onGranted={() => { setBuyerPrompt(false); navigate('/catalog'); }}
        />
      )}
    </header>
  );
};
