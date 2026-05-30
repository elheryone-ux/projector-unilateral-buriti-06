import React, { createContext, useContext, useEffect, useState } from "react";
import { adminAuth } from "./api";

const AuthContext = createContext(null);

export function AdminAuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = loading, null = unauth, obj = authed

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!adminAuth.getToken()) {
        if (mounted) setUser(null);
        return;
      }
      try {
        const u = await adminAuth.me();
        if (mounted) setUser(u);
      } catch {
        adminAuth.clearToken();
        if (mounted) setUser(null);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const login = async (username, password) => {
    const u = await adminAuth.login(username, password);
    setUser(u);
    return u;
  };

  const logout = async () => {
    await adminAuth.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAdminAuth = () => useContext(AuthContext);
