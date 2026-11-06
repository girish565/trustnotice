import { createContext, useContext, useEffect, useState } from "react"; import { api } from "../services/api";
const Ctx = createContext(null); export const useAuth = () => useContext(Ctx);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); const [ready, setReady] = useState(false);
  useEffect(() => { (localStorage.getItem("tn_token") ? api.me().then(setUser).catch(() => localStorage.removeItem("tn_token")) : Promise.resolve()).finally(() => setReady(true)); }, []);
  const login = async (e, p) => { const r = await api.login(e, p); localStorage.setItem("tn_token", r.access_token); const current = await api.me(); setUser(current); return current; };
  const logout = () => { localStorage.removeItem("tn_token"); setUser(null); };
  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}
