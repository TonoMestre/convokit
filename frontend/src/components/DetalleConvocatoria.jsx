import { useApp } from "../context/AppContext";
import EntregablePanel from "./EntregablePanel";

export default function DetalleConvocatoria() {
  const { activeConvocatoria, setActiveConvocatoria, deleteConvocatoria } = useApp();

  if (!activeConvocatoria) return null;

  const docs = activeConvocatoria.documentos_json ?? [];

  function handleEntregablesUpdate(nuevos) {
    setActiveConvocatoria((prev) => ({
      ...prev,
      entregables_json: { ...prev.entregables_json, ...nuevos },
    }));
  }

  function handleDelete() {
    if (confirm(`¿Eliminar la convocatoria "${activeConvocatoria.nombre}"? Esta acción no se puede deshacer.`)) {
      deleteConvocatoria(activeConvocatoria.id);
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-10 px-6 font-sans">
      {/* Cabecera */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="font-slab text-2xl font-bold text-brand-blue">
            {activeConvocatoria.nombre}
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            {new Date(activeConvocatoria.fecha_creacion).toLocaleDateString("es-ES", {
              day: "2-digit", month: "long", year: "numeric",
            })}
          </p>
        </div>
        <button
          onClick={handleDelete}
          className="text-xs text-gray-400 hover:text-brand-red transition-colors mt-1"
        >
          Eliminar
        </button>
      </div>

      {/* Documentos procesados */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
          Documentos procesados
        </h3>
        {docs.length === 0 ? (
          <p className="text-sm text-gray-400">Sin documentos.</p>
        ) : (
          <ul className="space-y-1">
            {docs.map((d, i) => (
              <li key={i} className="flex items-center gap-3 text-sm py-1.5" style={{ borderBottom: "1px solid var(--color-navy-20)" }}>
                <span className="font-medium text-gray-700 flex-1 truncate">{d.nombre_archivo}</span>
                <span className="text-xs text-brand-blue/60 px-2 py-0.5" style={{ background: "var(--color-navy-20)" }}>{d.etiqueta}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Entregables */}
      <EntregablePanel
        convocatoria={activeConvocatoria}
        onUpdate={handleEntregablesUpdate}
      />
    </div>
  );
}
