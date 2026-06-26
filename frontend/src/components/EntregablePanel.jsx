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

function EntregableItem({ salida, texto, isOpen, onToggle, onRegenerate, regenerating }) {
  const [copied, setCopied] = useState(false);

  function handleCopy(e) {
    e.stopPropagation();
    navigator.clipboard.writeText(texto);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload(e) {
    e.stopPropagation();
    downloadFile(texto, `salida_${salida.num}_${salida.label.replace(/\s+/g, "_")}.${salida.ext}`);
  }

  function handleRegenerate(e) {
    e.stopPropagation();
    onRegenerate();
  }

  return (
    <div className={`border-b border-gray-200 last:border-b-0 ${isOpen ? "bg-white" : ""}`}>
      {/* Cabecera — siempre visible */}
      <div
        onClick={onToggle}
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer select-none transition-colors ${
          isOpen ? "bg-brand-blue" : "bg-white hover:bg-gray-50"
        }`}
      >
        {/* Número */}
        <span
          className={`font-slab font-bold text-sm w-5 shrink-0 ${
            isOpen ? "text-white" : "text-brand-red"
          }`}
        >
          {salida.num}
        </span>

        {/* Título */}
        <span
          className={`font-slab font-semibold text-sm flex-1 ${
            isOpen ? "text-white" : "text-brand-blue"
          }`}
        >
          {salida.label}
        </span>

        {/* Botones de acción — siempre accesibles */}
        <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={handleCopy}
            className={`text-xs px-2.5 py-1 border transition-colors ${
              isOpen
                ? "border-white/40 text-white hover:bg-white hover:text-brand-blue"
                : "border-gray-300 text-gray-600 hover:border-brand-blue hover:text-brand-blue"
            }`}
          >
            {copied ? "¡Copiado!" : "Copiar"}
          </button>
          <button
            onClick={handleDownload}
            className={`text-xs px-2.5 py-1 border transition-colors ${
              isOpen
                ? "border-white/40 text-white hover:bg-white hover:text-brand-blue"
                : "border-gray-300 text-gray-600 hover:border-brand-blue hover:text-brand-blue"
            }`}
          >
            .{salida.ext}
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className={`text-xs px-2.5 py-1 border transition-colors disabled:opacity-40 ${
              isOpen
                ? "border-brand-red bg-brand-red text-white hover:opacity-80"
                : "border-brand-red text-brand-red hover:bg-brand-red hover:text-white"
            }`}
          >
            {regenerating ? "..." : "Regenerar"}
          </button>
        </div>

        {/* Chevron */}
        <span
          className={`text-xs shrink-0 ml-1 ${isOpen ? "text-white" : "text-gray-400"}`}
        >
          {isOpen ? "▲" : "▼"}
        </span>
      </div>

      {/* Contenido plegable */}
      {isOpen && (
        <div className="px-5 py-5 border-t border-gray-100">
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

  // Acordeón: solo un entregable abierto a la vez. null = todos cerrados.
  const [openNum, setOpenNum] = useState(null);
  const [selected, setSelected] = useState([]);
  const [generating, setGenerating] = useState({});
  const [error, setError] = useState(null);

  function toggleAccordion(num) {
    setOpenNum((prev) => (prev === num ? null : num));
  }

  function toggleSalida(num) {
    setSelected((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num]
    );
  }

  async function generate(types) {
    setError(null);
    setGenerating((prev) => ({ ...prev, ...Object.fromEntries(types.map((n) => [n, true])) }));

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
      // Abrir automáticamente el primero que se acabe de generar.
      if (types.length === 1) setOpenNum(types[0]);
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
  const generadas  = SALIDAS.filter((s) =>  entregables[String(s.num)]);

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

      {/* Acordeón de entregables generados */}
      {generadas.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide mb-3">
            Entregables generados
          </h3>
          <div className="border border-gray-200">
            {generadas.map((s) => (
              <EntregableItem
                key={s.num}
                salida={s}
                texto={entregables[String(s.num)]}
                isOpen={openNum === s.num}
                onToggle={() => toggleAccordion(s.num)}
                regenerating={!!generating[s.num]}
                onRegenerate={() => generate([s.num])}
              />
            ))}
          </div>
        </section>
      )}

      {generadas.length === 0 && pendientes.length === 0 && (
        <p className="text-sm text-gray-400 italic">No hay entregables disponibles.</p>
      )}
    </div>
  );
}
