import { useState } from "react";
import { useApp } from "../context/AppContext";

export default function LoginScreen() {
  const { login } = useApp();
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(password);
    } catch (err) {
      setError(err.message || "No se pudo iniciar sesión.");
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-brand-blue"
      style={{ padding: "24px" }}
    >
      <form
        onSubmit={handleSubmit}
        className="bg-white w-full flex flex-col"
        style={{ maxWidth: "380px", padding: "40px 36px", borderTop: "3px solid var(--color-red)" }}
      >
        <span
          style={{
            fontFamily: "var(--font-titles)",
            fontWeight: 700,
            fontSize: "26px",
            color: "var(--color-navy)",
            lineHeight: 1.1,
          }}
        >
          ConvoKit
        </span>
        <span
          style={{
            fontFamily: "var(--font-body)",
            fontSize: "11px",
            color: "var(--color-navy)",
            opacity: 0.6,
            letterSpacing: "0.15em",
            marginTop: "2px",
          }}
        >
          by innóvate 4.0
        </span>

        <p className="text-sm text-gray-600 mt-6">
          Herramienta de uso interno. Introduce la contraseña de acceso para continuar.
        </p>

        <label className="text-xs font-semibold text-brand-blue uppercase tracking-wide mt-5">
          Contraseña
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          className="mt-1 border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-brand-blue"
          style={{ borderRadius: 0 }}
        />

        {error && (
          <p className="text-xs mt-2" style={{ color: "var(--color-red)" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={!password || submitting}
          className="mt-5 bg-brand-red text-white text-sm font-semibold py-2.5 hover:bg-red-800 transition-colors disabled:opacity-40"
          style={{ borderRadius: 0 }}
        >
          {submitting ? "Comprobando..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
