import { createContext, useContext } from 'react';

// Ref-based (not state) so the 3D canvas can read it on every frame
// without triggering React re-renders.
const ScrollProgressCtx = createContext({ current: 0 });

export function ScrollProgressProvider({ children, progressRef }) {
  return (
    <ScrollProgressCtx.Provider value={progressRef}>
      {children}
    </ScrollProgressCtx.Provider>
  );
}

export const useScrollProgress = () => useContext(ScrollProgressCtx);
