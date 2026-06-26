import { useEffect, useState } from "react";

// Backend base URL. Configured via VITE_API_URL (see .env.example).
const API_URL = import.meta.env.VITE_API_URL;

// Minimal scaffold screen: shows the app name and checks backend connectivity
// by calling the /health endpoint. Real layout and flows arrive in later steps.
export default function App() {
  const [status, setStatus] = useState("checking"); // "checking" | "ok" | "error"

  useEffect(() => {
    if (!API_URL) {
      setStatus("error");
      return;
    }

    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data) => setStatus(data.status === "ok" ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const statusText = {
    checking: "Comprobando conexión con el backend...",
    ok: "Backend conectado correctamente.",
    error: "No se pudo conectar con el backend.",
  }[status];

  const statusColor = status === "ok" ? "text-brand-blue" : "text-brand-red";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-white">
      <h1 className="font-slab text-5xl font-bold text-brand-blue">ConvoKit</h1>
      <p className={`mt-4 text-base ${status === "checking" ? "text-black" : statusColor}`}>
        {statusText}
      </p>
    </div>
  );
}
