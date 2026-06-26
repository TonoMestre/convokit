import { createContext, useContext, useEffect, useState } from "react";

const AppContext = createContext(null);

const API = import.meta.env.VITE_API_URL;

export function AppProvider({ children }) {
  const [convocatorias, setConvocatorias] = useState([]);
  const [activeConvocatoria, setActiveConvocatoria] = useState(null); // detalle completo
  const [view, setView] = useState("nueva"); // "nueva" | "detalle"
  const [error, setError] = useState(null);

  async function loadConvocatorias() {
    try {
      const res = await fetch(`${API}/convocatorias`);
      if (!res.ok) throw new Error();
      setConvocatorias(await res.json());
    } catch {
      setError("No se pudo cargar el histórico de convocatorias.");
    }
  }

  async function openConvocatoria(id) {
    try {
      const res = await fetch(`${API}/convocatorias/${id}`);
      if (!res.ok) throw new Error();
      setActiveConvocatoria(await res.json());
      setView("detalle");
    } catch {
      setError("No se pudo cargar la convocatoria.");
    }
  }

  async function deleteConvocatoria(id) {
    try {
      const res = await fetch(`${API}/convocatorias/${id}`, { method: "DELETE" });
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
        API,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
