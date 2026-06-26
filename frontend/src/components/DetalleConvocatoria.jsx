import { useApp } from "../context/AppContext";

// Placeholder para el Paso 7 (visualización de entregables).
// Por ahora muestra el nombre, los documentos procesados y un botón de generación básico.

const SALIDAS = [
  { num: 1, label: "Guía interna del consultor" },
  { num: 2, label: "Ficha comercial para el cliente" },
  { num: 3, label: "Post de LinkedIn" },
  { num: 4, label: "Post WordPress con SEO" },
  { num: 5, label: "Landing page" },
  { num: 6, label: "Set de prompts para la memoria" },
  { num: 7, label: "Lista de documentación + correo al cliente" },
];

export default function DetalleConvocatoria() {
  const { activeConvocatoria } = useApp();

  if (!activeConvocatoria) return null;

  const docs = activeConvocatoria.documentos_json ?? [];
  const entregables = activeConvocatoria.entregables_json ?? {};

  return (
    <div className="max-w-3xl mx-auto py-10 px-6 font-sans">
      <h2 className="font-slab text-2xl font-bold text-brand-blue mb-1">
        {activeConvocatoria.nombre}
      </h2>
      <p className="text-xs text-gray-400 mb-8">
        {new Date(activeConvocatoria.fecha_creacion).toLocaleDateString("es-ES", {
          day: "2-digit", month: "long", year: "numeric",
        })}
      </p>

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
              <li key={i} className="flex items-center gap-3 text-sm border-b border-gray-100 py-1.5">
                <span className="font-medium text-gray-700 flex-1 truncate">{d.nombre_archivo}</span>
                <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5">{d.etiqueta}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Entregables — placeholder Paso 7 */}
      <section>
        <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
          Entregables
        </h3>
        <p className="text-sm text-gray-400 italic">
          La visualización y generación de entregables se implementa en el Paso 7.
        </p>
        {Object.keys(entregables).length > 0 && (
          <ul className="mt-3 space-y-1">
            {SALIDAS.filter((s) => entregables[String(s.num)]).map((s) => (
              <li key={s.num} className="flex items-center gap-2 text-sm">
                <span className="w-2 h-2 bg-brand-red inline-block" />
                <span className="text-gray-700">{s.label}</span>
                <span className="text-xs text-green-600 ml-auto">Generado</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
