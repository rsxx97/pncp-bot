import { createContext, useContext, useEffect, useState, useCallback } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [tenant, setTenant] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("token");
    const u = localStorage.getItem("tenant");
    if (t && u) {
      try {
        setToken(t);
        setTenant(JSON.parse(u));
        // Refresca campos novos do tenant (plano_radar_limite etc) do /me
        fetch("/api/auth/me", { headers: { Authorization: `Bearer ${t}` } })
          .then(r => r.ok ? r.json() : null)
          .then(fresh => {
            if (fresh) {
              setTenant(prev => ({ ...prev, ...fresh }));
              localStorage.setItem("tenant", JSON.stringify({ ...JSON.parse(u), ...fresh }));
            }
          })
          .catch(() => {});
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("tenant");
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback((newTenant, newToken) => {
    localStorage.setItem("token", newToken);
    localStorage.setItem("tenant", JSON.stringify(newTenant));
    setToken(newToken);
    setTenant(newTenant);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("tenant");
    setToken(null);
    setTenant(null);
  }, []);

  const isAdmin = tenant?.role === "super_admin";

  return (
    <AuthContext.Provider value={{ tenant, token, loading, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
