import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { publicApi } from '../sync/api';
import { readFlag, writeFlag } from '../lib/siteFlags';

// Same source and cache as the header: /api/sync/pricing `library_visible`.
export default function useCatalogVisible() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [visible, setVisible] = useState(() => readFlag('library_visible', false));
  useEffect(() => {
    if (!isLoaded) return undefined;
    const signedIn = !!isSignedIn;
    setVisible(readFlag('library_visible', signedIn));
    let alive = true;
    publicApi.pricing(getToken, isSignedIn)
      .then((d) => {
        if (!alive) return;
        setVisible(!!d.library_visible);
        writeFlag('library_visible', signedIn, !!d.library_visible);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [getToken, isSignedIn, isLoaded]);
  return visible;
}
