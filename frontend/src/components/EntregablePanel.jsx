import { useState } from "react";
import { useApp } from "../context/AppContext";

const SALIDAS = [
  { num: 1, label: "Guía interna del consultor", ext: "md" },
  { num: 2, label: "Ficha comercial para el cliente", ext: "md" },
  { num: 3, label: "Landing page", ext: "md" },
  { num: 4, label: "Set de prompts para la memoria", ext: "md", hasJson: true },
  { num: 5, label: "Lista de documentación + correo al cliente", ext: "md", hasJson: true },
];

function downloadFile(content, filename) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function EntregableItem({ salida, texto, onRegenerate, regenerating }) {
  const [open, setOpen] = useState(true);
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(texto);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    downloadFile(texto, `salida_${salida.num}_${salida.label.replace(/\s+/g, "_")}.${salida.ext}`);
  }

  return (
    <div className="border border-gray-200 mb-3">
      {/* Cabecera del panel */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-left flex-1"
        >
          <span className="text-brand-red font-bold text-sm w-5">{salida.num}</span>
          <span className="font-semibold text-brand-blue text-sm">{salida.label}</span>
          <span className="ml-1 text-gray-400 text-xs">{open ? "▲" : "▼"}</span>
        </button>
        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={handleCopy}
            className="text-xs px-3 py-1 border border-gray-300 hover:border-brand-blue hover:text-brand-blue transition-colors"
          >
            {copied ? "¡Copiado!" : "Copiar"}
          </button>
          <button
            onClick={handleDownload}
            className="text-xs px-3 py-1 border border-gray-300 hover:border-brand-blue hover:text-brand-blue transition-colors"
          >
            .{salida.ext}
          </button>
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="text-xs px-3 py-1 border border-brand-red text-brand-red hover:bg-brand-red hover:text-white transition-colors disabled:opacity-40"
          >
            {regenerating ? "..." : "Regenerar"}
          </button>
        </div>
      </div>

      {/* Contenido */}
      {open && (
        <div className="px-4 py-4">
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed">
            {texto}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function EntregablePanel({ convocatoria, onUpdate }) {
  const { API } = useApp();
  const entregables = convocatoria.entregables_json ?? {};

  const [selected, setSelected] = useState([]);
  const [generating, setGenerating] = useState({}); // { num: true/false }
  const [error, setError] = useState(null);

  function toggleSalida(num) {
    setSelected((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num]
    );
  }

  async function generate(types) {
    setError(null);
    const loadingState = Object.fromEntries(types.map((n) => [n, true]));
    setGenerating((prev) => ({ ...prev, ...loadingState }));

    try {
      const res = await fetch(`${API}/convocatorias/${convocatoria.id}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_types: types }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Error al generar.");
      onUpdate(data.entregables);
      setSelected([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating((prev) => {
        const next = { ...prev };
        types.forEach((n) => delete next[n]);
        return next;
      });
    }
  }

  const pendientes = SALIDAS.filter((s) => !entregables[String(s.num)]);
  const generadas = SALIDAS.filter((s) => entregables[String(s.num)]);

  return (
    <div>
      {error && (
        <div className="bg-brand-red text-white text-sm px-4 py-3 mb-4">{error}</div>
      )}

      {/* Selector de entregables pendientes */}
      {pendientes.length > 0 && (
        <section className="mb-8">
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
            Generar entregables
          </h3>
          <div className="space-y-2 mb-4">
            {pendientes.map((s) => (
              <label key={s.num} className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={selected.includes(s.num)}
                  onChange={() => toggleSalida(s.num)}
                  className="accent-brand-red w-4 h-4"
                />
                <span className="text-sm text-gray-700 group-hover:text-brand-blue transition-colors">
                  <span className="font-semibold text-brand-red mr-1">{s.num}.</span>
                  {s.label}
                </span>
                {generating[s.num] && (
                  <span className="text-xs text-gray-400 italic">Generando...</span>
                )}
              </label>
            ))}
          </div>
          <button
            onClick={() => generate(selected)}
            disabled={selected.length === 0 || Object.keys(generating).length > 0}
            className="bg-brand-blue text-white text-sm font-semibold px-5 py-2 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          >
            Generar seleccionados
          </button>
        </section>
      )}

      {/* Entregables ya generados */}
      {generadas.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
            Entregables generados
          </h3>
          {generadas.map((s) => (
            <EntregableItem
              key={s.num}
              salida={s}
              texto={entregables[String(s.num)]}
              regenerating={!!generating[s.num]}
              onRegenerate={() => generate([s.num])}
            />
          ))}
        </section>
      )}

      {generadas.length === 0 && pendientes.length === 0 && (
        <p className="text-sm text-gray-400 italic">No hay entregables disponibles.</p>
      )}
    </div>
  );
}
