import { useApp } from "../context/AppContext";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function Sidebar() {
  const { convocatorias, activeConvocatoria, openConvocatoria, deleteConvocatoria, startNueva } = useApp();

  return (
    <aside className="w-64 min-h-screen bg-brand-blue flex flex-col font-sans">
      {/* Logo / título */}
      <div className="px-5 py-5 border-b border-white/20">
        <h1 className="font-slab text-white text-xl font-bold tracking-wide">ConvoKit</h1>
        <p className="text-white/60 text-xs mt-0.5">Innóvate 4.0</p>
      </div>

      {/* Botón nueva convocatoria */}
      <div className="px-4 py-4">
        <button
          onClick={startNueva}
          className="w-full bg-brand-red text-white text-sm font-semibold py-2 px-3 hover:opacity-90 transition-opacity"
        >
          + Nueva convocatoria
        </button>
      </div>

      {/* Histórico */}
      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        {convocatorias.length === 0 ? (
          <p className="text-white/40 text-xs px-2 mt-2">Sin convocatorias aún.</p>
        ) : (
          <ul className="space-y-1">
            {convocatorias.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => openConvocatoria(c.id)}
                  className={`w-full text-left px-3 py-2.5 text-sm transition-colors group ${
                    activeConvocatoria?.id === c.id
                      ? "bg-white/20 text-white"
                      : "text-white/70 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <span className="block truncate font-medium">{c.nombre}</span>
                  <span className="block text-xs text-white/40 mt-0.5">{formatDate(c.fecha_creacion)}</span>
                  {c.entregables_disponibles.length > 0 && (
                    <span className="block text-xs text-brand-red/80 mt-0.5">
                      {c.entregables_disponibles.length} entregable{c.entregables_disponibles.length > 1 ? "s" : ""}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  );
}
