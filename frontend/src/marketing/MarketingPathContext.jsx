import { createContext, useContext, useState } from 'react';

const PathCtx = createContext({ path: null, setPath: () => {} });

export function MarketingPathProvider({ children }) {
  const [path, setPath] = useState(null);
  return <PathCtx.Provider value={{ path, setPath }}>{children}</PathCtx.Provider>;
}

export const useMarketingPath = () => useContext(PathCtx);
