import { useApp } from "../context/AppContext";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatCost(eur) {
  if (!eur || eur === 0) return null;
  return eur < 0.01 ? "<0.01 €" : `${eur.toFixed(3)} €`;
}

export default function Sidebar() {
  const {
    convocatorias,
    activeConvocatoria,
    view,
    openConvocatoria,
    startNueva,
    openStats,
  } = useApp();

  return (
    <aside
      className="w-64 flex flex-col font-sans bg-brand-blue overflow-y-auto shrink-0"
      style={{ borderRight: "1px solid var(--color-navy-20)" }}
    >
      {/* Nueva convocatoria */}
      <div className="px-4 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
        <button
          onClick={startNueva}
          className="btn-primary w-full bg-brand-red text-white text-sm font-semibold py-2.5 px-3 hover:opacity-90 transition-opacity"
        >
          + Nueva convocatoria
        </button>
      </div>

      {/* Histórico */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {convocatorias.length === 0 ? (
          <p className="text-white/40 text-xs px-3 mt-2">Sin convocatorias aún.</p>
        ) : (
          <ul className="space-y-0.5">
            {convocatorias.map((c) => {
              const isActive = activeConvocatoria?.id === c.id;
              const cost = formatCost(c.total_cost_eur);
              return (
                <li key={c.id}>
                  <button
                    onClick={() => openConvocatoria(c.id)}
                    className={`w-full text-left py-2.5 pr-3 text-sm transition-colors border-l-2 ${
                      isActive
                        ? "border-brand-red pl-[10px] bg-white/10 text-white"
                        : "border-transparent pl-3 text-white/70 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    <span className="block truncate font-medium">{c.nombre}</span>
                    <span className="block text-xs text-white/40 mt-0.5">
                      {formatDate(c.fecha_creacion)}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      {c.entregables_disponibles.length > 0 && (
                        <span className="text-xs text-brand-red/80">
                          {c.entregables_disponibles.length} entregable
                          {c.entregables_disponibles.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {cost && (
                        <span className="text-xs text-white/30">{cost}</span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>

      {/* Estadísticas */}
      <div
        className="px-4 py-4 shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}
      >
        <button
          onClick={openStats}
          className={`w-full text-left text-xs px-0 py-1 transition-colors border-l-2 pl-2 ${
            view === "stats"
              ? "border-brand-red text-white"
              : "border-transparent text-white/50 hover:text-white"
          }`}
        >
          Estadísticas de API
        </button>
      </div>
    </aside>
  );
}
