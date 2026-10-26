import { useEffect, useState } from 'react';
import { getCurrentChoice, subscribeChoice } from '../lib/consent';

// The choice in force: undefined while loading, null when nobody has chosen.
export default function useConsent() {
  const [choice, setChoice] = useState(getCurrentChoice());
  useEffect(() => {
    // The manager may have set the choice between this render and this effect.
    setChoice(getCurrentChoice());
    return subscribeChoice(setChoice);
  }, []);
  return choice;
}
