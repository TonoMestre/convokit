import { createContext, useContext, useEffect, useState } from "react";

const AppContext = createContext(null);

const API = import.meta.env.VITE_API_URL;
const TOKEN_KEY = "convokit_token";

export function AppProvider({ children }) {
  const [convocatorias, setConvocatorias] = useState([]);
  const [activeConvocatoria, setActiveConvocatoria] = useState(null); // detalle completo
  const [view, setView] = useState("nueva"); // "nueva" | "detalle" | "stats"
  const [error, setError] = useState(null);
  const [authNeeded, setAuthNeeded] = useState(false);

  // Wrapper de fetch que añade el token de sesión (si existe) y, ante un 401
  // del backend, borra el token y muestra la pantalla de acceso. Si el backend
  // no tiene APP_PASSWORD configurada nunca responde 401 y la app funciona
  // sin login, como hasta ahora.
  async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      setAuthNeeded(true);
    }
    return res;
  }

  async function login(password) {
    const res = await fetch(`${API}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "No se pudo iniciar sesión.");
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.token);
    setAuthNeeded(false);
    setError(null);
    await loadConvocatorias();
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setConvocatorias([]);
    setActiveConvocatoria(null);
    setView("nueva");
    setAuthNeeded(true);
  }

  async function loadConvocatorias() {
    try {
      const res = await apiFetch(`${API}/convocatorias`);
      if (res.status === 401) return; // apiFetch ya ha activado la pantalla de acceso
      if (!res.ok) throw new Error();
      setConvocatorias(await res.json());
    } catch {
      setError("No se pudo cargar el histórico de convocatorias.");
    }
  }

  async function openConvocatoria(id) {
    try {
      const res = await apiFetch(`${API}/convocatorias/${id}`);
      if (res.status === 401) return;
      if (!res.ok) throw new Error();
      setActiveConvocatoria(await res.json());
      setView("detalle");
    } catch {
      setError("No se pudo cargar la convocatoria.");
    }
  }

  async function deleteConvocatoria(id) {
    try {
      const res = await apiFetch(`${API}/convocatorias/${id}`, { method: "DELETE" });
      if (res.status === 401) return;
      if (!res.ok) throw new Error();
      if (activeConvocatoria?.id === id) {
        setActiveConvocatoria(null);
        setView("nueva");
      }
      await loadConvocatorias();
    } catch {
      setError("No se pudo eliminar la convocatoria.");
    }
  }

  function startNueva() {
    setActiveConvocatoria(null);
    setView("nueva");
  }

  function openStats() {
    setActiveConvocatoria(null);
    setView("stats");
  }

  function clearError() {
    setError(null);
  }

  useEffect(() => {
    loadConvocatorias();
  }, []);

  return (
    <AppContext.Provider
      value={{
        convocatorias,
        activeConvocatoria,
        setActiveConvocatoria,
        view,
        error,
        clearError,
        loadConvocatorias,
        openConvocatoria,
        deleteConvocatoria,
        startNueva,
        openStats,
        API,
        apiFetch,
        authNeeded,
        login,
        logout,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
