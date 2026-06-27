import { useState, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";

const SALIDAS = [
  { num: 1, label: "Guía interna del consultor", ext: "md" },
  { num: 2, label: "Ficha comercial para el cliente", ext: "md" },
  { num: 3, label: "Landing page", ext: "md", hasJson: false, hasMode: true },
  { num: 4, label: "Set de prompts para la memoria", ext: "md", hasJson: true },
  { num: 5, label: "Lista de documentación + correo al cliente", ext: "md", hasJson: true },
];

function Spinner({ className = "" }) {
  return (
    <span
      className={`inline-block border-2 border-current border-t-transparent rounded-full animate-spin ${className}`}
      aria-hidden="true"
    />
  );
}

function downloadFile(content, filename) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function InstruccionesField({ num, instructions, setInstructions, placeholder }) {
  return (
    <textarea
      value={instructions[num] || ""}
      onChange={(e) => setInstructions((prev) => ({ ...prev, [num]: e.target.value }))}
      placeholder={placeholder}
      rows={2}
      className="mt-1 w-full text-xs border border-gray-200 px-2 py-1.5 text-gray-700 resize-none focus:outline-none focus:border-brand-blue"
    />
  );
}

function PendingSalidaRow({
  salida, selected, onToggle, outputStatuses, output4Progress,
  instructions, setInstructions, instructionsOpen, setInstructionsOpen, mode3, setMode3,
}) {
  const isChecked = selected.includes(salida.num);
  const outputStatus = outputStatuses[String(salida.num)]?.status;
  const isRunning = outputStatus === "queued" || outputStatus === "running";

  function toggleInstructions() {
    const isOpen = !!instructionsOpen[salida.num];
    const hasText = !!(instructions[salida.num] || "").trim();
    if (isOpen && !hasText) {
      setInstructionsOpen((prev) => ({ ...prev, [salida.num]: false }));
    } else {
      setInstructionsOpen((prev) => ({ ...prev, [salida.num]: !isOpen }));
    }
  }

  const instrOpen = !!instructionsOpen[salida.num];
  const hasInstr = !!(instructions[salida.num] || "").trim();

  let statusLabel = null;
  if (outputStatus === "queued") {
    statusLabel = "En cola...";
  } else if (outputStatus === "running") {
    if (salida.num === 4 && output4Progress) {
      statusLabel = output4Progress.actual === 0
        ? "Identificando apartados..."
        : `Apartado ${output4Progress.actual} de ${output4Progress.total}`;
    } else {
      statusLabel = "Generando...";
    }
  }

  return (
    <div className="py-1.5">
      <label className="flex items-center gap-3 cursor-pointer group">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={onToggle}
          disabled={isRunning}
          className="accent-brand-red w-4 h-4 shrink-0"
        />
        <span className="text-sm text-gray-700 group-hover:text-brand-blue transition-colors flex-1">
          <span className="font-semibold text-brand-red mr-1">{salida.num}.</span>
          {salida.label}
        </span>
        {isRunning && (
          <span className="flex items-center gap-1.5 text-xs text-brand-red shrink-0">
            <Spinner className="w-3 h-3" />
            {statusLabel}
          </span>
        )}
      </label>

      {isChecked && (
        <div className="ml-7 mt-2 space-y-2">
          {salida.hasMode ? (
            <>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-gray-500 font-medium">Modo de generación</span>
                <div className="flex flex-col gap-1">
                  {[
                    { value: "ABIERTA", label: "Convocatoria abierta o inminente" },
                    { value: "ANTICIPADA", label: "Posicionamiento anticipado (edición futura)" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer text-xs text-gray-700">
                      <input
                        type="radio"
                        name="mode3"
                        value={opt.value}
                        checked={mode3 === opt.value}
                        onChange={() => setMode3(opt.value)}
                        className="accent-brand-red"
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 font-medium">
                  Instrucciones adicionales <span className="font-normal">(opcional)</span>
                </label>
                <InstruccionesField
                  num={salida.num}
                  instructions={instructions}
                  setInstructions={setInstructions}
                  placeholder="Ej: enfoca el CTA hacia empresas del sector metalmecánico"
                />
              </div>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={toggleInstructions}
                className={`text-xs transition-colors ${
                  hasInstr ? "text-brand-blue font-medium" : "text-gray-400 hover:text-brand-blue"
                }`}
              >
                {instrOpen
                  ? "− Instrucciones adicionales"
                  : hasInstr
                  ? "✓ Instrucciones añadidas"
                  : "+ Añadir instrucciones"}
              </button>
              {instrOpen && (
                <InstruccionesField
                  num={salida.num}
                  instructions={instructions}
                  setInstructions={setInstructions}
                  placeholder="Ej: el cliente ya tiene Perfil Estratégico, incluirlo como fuente principal"
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ítem de acordeón para entregables ya generados
// ---------------------------------------------------------------------------

function EntregableItem({
  salida, texto, hasJsonData, convocatoriaId, isOpen, onToggle,
  onRegenerate, outputStatus, output4Progress, costEur,
}) {
  const { API } = useApp();
  const [copied, setCopied] = useState(false);
  const [downloadingJson, setDownloadingJson] = useState(false);

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

  async function handleDownloadJson(e) {
    e.stopPropagation();
    setDownloadingJson(true);
    try {
      const res = await fetch(`${API}/convocatorias/${convocatoriaId}/json/${salida.num}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.detail ?? "Error al descargar el JSON.");
        return;
      }
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `salida_${salida.num}_${salida.label.replace(/\s+/g, "_")}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingJson(false);
    }
  }

  const isRegenerating = outputStatus === "queued" || outputStatus === "running";
  const open = isOpen;
  const btnBase = "text-xs px-2.5 py-1 border transition-colors";
  const btnDark = "border-white/40 text-white hover:bg-white hover:text-brand-blue";
  const btnLight = "border-gray-300 text-gray-600 hover:border-brand-blue hover:text-brand-blue";

  let loadingMsg = "Generando...";
  if (outputStatus === "queued") {
    loadingMsg = "En cola...";
  } else if (outputStatus === "running" && salida.num === 4 && output4Progress) {
    loadingMsg = output4Progress.actual === 0
      ? "Identificando apartados..."
      : `Apartado ${output4Progress.actual} de ${output4Progress.total}`;
  }

  return (
    <div className={`border-b border-gray-200 last:border-b-0 ${open ? "bg-white" : ""}`}>
      <div
        onClick={onToggle}
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer select-none transition-colors ${
          open ? "bg-brand-blue" : "bg-white hover:bg-gray-50"
        }`}
      >
        <span className={`font-slab font-bold text-sm w-5 shrink-0 ${open ? "text-white" : "text-brand-red"}`}>
          {salida.num}
        </span>
        <span className={`font-slab font-semibold text-sm flex-1 ${open ? "text-white" : "text-brand-blue"}`}>
          {salida.label}
        </span>

        <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
          {/* Coste de la última generación */}
          {costEur != null && !isRegenerating && (
            <span className={`text-xs ${open ? "text-white/50" : "text-gray-400"}`}>
              {costEur < 0.01
                ? `<0.01 €`
                : `${costEur.toFixed(3)} €`}
            </span>
          )}

          <button onClick={handleCopy} className={`${btnBase} ${open ? btnDark : btnLight}`}>
            {copied ? "¡Copiado!" : "Copiar"}
          </button>
          <button onClick={handleDownload} className={`${btnBase} ${open ? btnDark : btnLight}`}>
            .{salida.ext}
          </button>
          {salida.hasJson && hasJsonData && (
            <button
              onClick={handleDownloadJson}
              disabled={downloadingJson}
              className={`${btnBase} disabled:opacity-40 ${open ? btnDark : btnLight}`}
            >
              {downloadingJson ? <Spinner className="w-3 h-3" /> : ".json"}
            </button>
          )}

          {isRegenerating ? (
            <span className={`flex items-center gap-1.5 text-xs ${open ? "text-white" : "text-brand-red"}`}>
              <Spinner className="w-3 h-3" />
              <span className="whitespace-nowrap">{loadingMsg}</span>
            </span>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); onRegenerate(); }}
              className={`${btnBase} ${
                open
                  ? "border-brand-red bg-brand-red text-white hover:opacity-80"
                  : "border-brand-red text-brand-red hover:bg-brand-red hover:text-white"
              }`}
            >
              Regenerar
            </button>
          )}
        </div>

        <span className={`text-xs shrink-0 ml-1 ${open ? "text-white" : "text-gray-400"}`}>
          {open ? "▲" : "▼"}
        </span>
      </div>

      {open && (
        <div className="px-5 py-5 border-t border-gray-100">
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed">
            {texto}
          </pre>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel principal
// ---------------------------------------------------------------------------

export default function EntregablePanel({ convocatoria, onUpdate: _onUpdate }) {
  const { API, openConvocatoria } = useApp();
  const entregables = convocatoria.entregables_json ?? {};

  const [openNum, setOpenNum] = useState(null);
  const [selected, setSelected] = useState([]);
  // { "1": {status: "queued"|"running"|"completed"|"error", cost_eur?: number} }
  const [outputStatuses, setOutputStatuses] = useState({});
  const [output4Progress, setOutput4Progress] = useState(null);
  const [error, setError] = useState(null);

  const [instructions, setInstructions] = useState({});
  const [instructionsOpen, setInstructionsOpen] = useState({});
  const [mode3, setMode3] = useState("ABIERTA");

  const pollRef = useRef(null);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => () => stopPolling(), []);

  function toggleAccordion(num) {
    setOpenNum((prev) => (prev === num ? null : num));
  }

  function toggleSalida(num) {
    setSelected((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num]
    );
  }

  function isAnyRunning() {
    return Object.values(outputStatuses).some(
      (s) => s.status === "queued" || s.status === "running"
    );
  }

  async function pollJob(jobId, types) {
    try {
      const res = await fetch(`${API}/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();
      const { status, progress } = job;

      const outputs = progress?.outputs || {};
      setOutputStatuses(outputs);

      const p4 = progress?.output4_progress;
      setOutput4Progress(p4 || null);

      if (status === "completed" || status === "error") {
        stopPolling();
        setSelected([]);
        if (types.length === 1 && status === "completed") {
          setOpenNum(types[0]);
        }
        if (status === "error" && !Object.values(outputs).some((o) => o.status === "completed")) {
          setError("Ha ocurrido un error durante la generación.");
        }
        await openConvocatoria(convocatoria.id);
      }
    } catch {
      // transient network error, keep polling
    }
  }

  async function generate(types, overrideInstructions) {
    stopPolling();
    setError(null);
    setOutput4Progress(null);

    const instrMap = overrideInstructions ?? instructions;

    const initialStatuses = {};
    types.forEach((t) => { initialStatuses[String(t)] = { status: "queued" }; });
    setOutputStatuses(initialStatuses);

    const salidas = types.map((t) => ({
      output_type: t,
      instrucciones_adicionales: instrMap[t] || "",
      ...(t === 3 ? { modo: mode3 } : {}),
    }));

    try {
      const res = await fetch(`${API}/convocatorias/${convocatoria.id}/generate/async`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ salidas }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "Error al iniciar la generación.");
      }

      const { job_id } = await res.json();

      // Primera consulta inmediata, luego cada 2s
      await pollJob(job_id, types);
      pollRef.current = setInterval(() => pollJob(job_id, types), 2000);
    } catch (err) {
      setError(err.message);
      setOutputStatuses({});
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
          <div className="mb-4 divide-y divide-gray-100">
            {pendientes.map((s) => (
              <PendingSalidaRow
                key={s.num}
                salida={s}
                selected={selected}
                onToggle={() => toggleSalida(s.num)}
                outputStatuses={outputStatuses}
                output4Progress={output4Progress}
                instructions={instructions}
                setInstructions={setInstructions}
                instructionsOpen={instructionsOpen}
                setInstructionsOpen={setInstructionsOpen}
                mode3={mode3}
                setMode3={setMode3}
              />
            ))}
          </div>
          <button
            onClick={() => generate(selected)}
            disabled={selected.length === 0 || isAnyRunning()}
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
            {generadas.map((s) => {
              const salStatus = outputStatuses[String(s.num)];
              return (
                <EntregableItem
                  key={s.num}
                  salida={s}
                  texto={entregables[String(s.num)]}
                  hasJsonData={!!entregables[`${s.num}_json`]}
                  convocatoriaId={convocatoria.id}
                  isOpen={openNum === s.num}
                  onToggle={() => toggleAccordion(s.num)}
                  outputStatus={salStatus?.status}
                  output4Progress={s.num === 4 ? output4Progress : null}
                  costEur={salStatus?.cost_eur ?? null}
                  onRegenerate={() => generate([s.num])}
                />
              );
            })}
          </div>
        </section>
      )}

      {generadas.length === 0 && pendientes.length === 0 && (
        <p className="text-sm text-gray-400 italic">No hay entregables disponibles.</p>
      )}
    </div>
  );
}
