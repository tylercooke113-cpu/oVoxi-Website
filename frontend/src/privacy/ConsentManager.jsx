import { useEffect, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';
import {
  fetchAccountChoice, gpcOn, postChoice, readVisitChoice, saveVisitChoice, setCurrentChoice,
} from '../lib/consent';

// Works out which choice is in force (Brief 26, decisions 1 to 3) and keeps it in the
// shared store. Renders nothing.
//   Signed out: this visit's choice, else null (the prompt asks).
//   Signed in: the account's saved choice wins and replaces the visit's. An account with
//   none takes the visit's choice (source "signup"); with neither, the prompt asks once.
//   GPC on and an account choice that allows advertising: a "gpc" row turns it off.
export default function ConsentManager() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  // Run once per sign-in state, even if Clerk hands back a new getToken on re-render.
  const tokenRef = useRef(getToken);
  tokenRef.current = getToken;

  useEffect(() => {
    if (!isLoaded) return undefined;
    if (!isSignedIn) {
      setCurrentChoice(readVisitChoice());
      return undefined;
    }
    let cancelled = false;
    const token = () => tokenRef.current();
    const auth = { getToken: token, isSignedIn: true };
    (async () => {
      try {
        let account = await fetchAccountChoice(token);
        if (!account) {
          const visit = readVisitChoice();
          if (!visit) { if (!cancelled) setCurrentChoice(null); return; }
          account = (await postChoice({ ...visit, source: 'signup' }, auth)).choice || visit;
        } else if (gpcOn() && account.advertising) {
          account = (await postChoice({ ...account, advertising: false, source: 'gpc' }, auth)).choice || account;
        }
        if (cancelled) return;
        setCurrentChoice(saveVisitChoice({
          analytics: account.analytics, advertising: account.advertising,
          source: 'account', decided_at: account.created_at || account.decided_at,
        }));
      } catch {
        // Backend unreachable: fall back to this visit's choice (or ask).
        if (!cancelled) setCurrentChoice(readVisitChoice());
      }
    })();
    return () => { cancelled = true; };
  }, [isLoaded, isSignedIn]);

  return null;
}
