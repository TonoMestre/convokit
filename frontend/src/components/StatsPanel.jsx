import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";

function StatCard({ label, value, sub }) {
  return (
    <div className="px-5 py-4" style={{ border: "1px solid var(--color-navy-20)" }}>
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-2xl font-slab font-bold text-brand-blue">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

const SALIDA_LABELS = {
  "1": "Guía del consultor",
  "2": "Ficha comercial",
  "3": "Landing page",
  "4": "Set de prompts",
  "5": "Documentación + correo",
};

export default function StatsPanel() {
  const { API } = useApp();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API}/stats`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!cancelled) setStats(data);
      } catch {
        if (!cancelled) setError("No se pudieron cargar las estadísticas.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [API]);

  if (loading) {
    return (
      <div className="p-8 text-sm text-gray-400">Cargando estadísticas...</div>
    );
  }
  if (error) {
    return (
      <div className="p-8 text-sm text-brand-red">{error}</div>
    );
  }
  if (!stats) return null;

  return (
    <div className="p-8 max-w-2xl">
      <h2 className="font-slab text-xl font-bold text-brand-blue mb-6">
        Estadísticas de uso de la API
      </h2>

      {/* Resumen global */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Gasto total"
          value={`${stats.total_cost_eur.toFixed(4)} €`}
        />
        <StatCard
          label="Llamadas totales"
          value={stats.total_calls}
        />
        <StatCard
          label="Convocatorias"
          value={stats.total_convocatorias}
        />
      </div>

      {/* Por salida */}
      {stats.by_output.length > 0 && (
        <div className="mb-8">
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
            Gasto por salida
          </h3>
          <div style={{ border: "1px solid var(--color-navy-20)" }}>
            {stats.by_output.map((row) => (
              <div key={row.salida} className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--color-navy-20)" }}>
                <div>
                  <span className="font-semibold text-brand-red text-sm mr-2">{row.salida}.</span>
                  <span className="text-sm text-gray-700">
                    {SALIDA_LABELS[row.salida] ?? `Salida ${row.salida}`}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-semibold text-brand-blue">
                    {row.total_cost_eur.toFixed(4)} €
                  </span>
                  <span className="text-xs text-gray-400 ml-2">
                    ({row.calls} llamada{row.calls !== 1 ? "s" : ""})
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Por modelo */}
      {stats.by_model.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
            Gasto por modelo
          </h3>
          <div style={{ border: "1px solid var(--color-navy-20)" }}>
            {stats.by_model.map((row) => (
              <div key={row.modelo} className="px-4 py-3" style={{ borderBottom: "1px solid var(--color-navy-20)" }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-700">{row.modelo}</span>
                  <span className="text-sm font-semibold text-brand-blue">
                    {row.total_cost_eur.toFixed(4)} €
                  </span>
                </div>
                <div className="text-xs text-gray-400">
                  {row.calls} llamada{row.calls !== 1 ? "s" : ""} ·{" "}
                  {(row.total_input_tokens / 1000).toFixed(1)}k tokens entrada ·{" "}
                  {(row.total_output_tokens / 1000).toFixed(1)}k tokens salida
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats.total_calls === 0 && (
        <p className="text-sm text-gray-400 italic">
          Aún no se han registrado llamadas a la API en esta instalación.
        </p>
      )}
    </div>
  );
}
