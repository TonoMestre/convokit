import { useState, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";

const SALIDAS = [
  { num: 1, label: "Guía interna del consultor",                  ext: "md" },
  { num: 2, label: "Ficha comercial para el cliente",             ext: "md" },
  { num: 3, label: "Landing page",                                ext: "html", hasMode: true, isHtml: true },
  { num: 4, label: "Set de prompts para la memoria",              ext: "md", hasJson: true },
  { num: 5, label: "Lista de documentación + correo al cliente",  ext: "md", hasJson: true },
  { num: 6, label: "Evaluador de encaje (HTML interactivo)",      ext: "html", isHtml: true },
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

const INSTR_PLACEHOLDER =
  "Instrucción adicional opcional: p.ej. 'El año correcto es 2026', 'No incluyas el apartado X'";

function InstruccionesField({ value, onChange }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={INSTR_PLACEHOLDER}
      rows={2}
      className="textarea-brand mt-1"
    />
  );
}

function PendingSalidaRow({
  salida, selected, onToggle, outputStatuses, output4Progress,
  instructions, setInstructions, mode3, setMode3, variant3, setVariant3,
  incluirEvaluador3, setIncluirEvaluador3,
}) {
  const isChecked = selected.includes(salida.num);
  const outputStatus = outputStatuses[String(salida.num)]?.status;
  const isRunning = outputStatus === "queued" || outputStatus === "running";

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
    <div className="py-2">
      <label className="flex items-center gap-3 cursor-pointer group">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={onToggle}
          disabled={isRunning}
          className="w-4 h-4 shrink-0"
          style={{ accentColor: "var(--color-navy)" }}
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
          {salida.hasMode && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-brand-blue uppercase tracking-wide">
                Modo de generación
              </span>
              <div className="flex flex-col gap-1">
                {[
                  { value: "ABIERTA",    label: "Convocatoria abierta o inminente" },
                  { value: "ANTICIPADA", label: "Posicionamiento anticipado (edición futura)" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 cursor-pointer text-xs text-gray-700">
                    <input
                      type="radio"
                      name="mode3"
                      value={opt.value}
                      checked={mode3 === opt.value}
                      onChange={() => setMode3(opt.value)}
                      style={{ accentColor: "var(--color-navy)" }}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          )}
          {salida.num === 3 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-brand-blue uppercase tracking-wide">
                Variante de distribución
              </span>
              <div className="flex flex-wrap gap-2">
                {VARIANT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setVariant3(opt.value)}
                    title={opt.hint}
                    className={`text-xs px-3 py-1.5 border transition-colors ${
                      variant3 === opt.value
                        ? "bg-brand-blue text-white border-brand-blue font-semibold"
                        : "bg-white text-brand-blue border-brand-blue/40 hover:border-brand-blue"
                    }`}
                    style={{ borderRadius: 0 }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-500">
                {VARIANT_OPTIONS.find((o) => o.value === variant3)?.hint}. Podrás cambiarla luego en la vista previa.
              </span>
              <label className="flex items-start gap-2 cursor-pointer text-xs text-gray-700 mt-2">
                <input
                  type="checkbox"
                  checked={incluirEvaluador3}
                  onChange={(e) => setIncluirEvaluador3(e.target.checked)}
                  className="w-4 h-4 shrink-0 mt-0.5"
                  style={{ accentColor: "var(--color-navy)" }}
                />
                <span>
                  Incluir el evaluador de encaje embebido en la landing (comparte las mismas
                  preguntas que la salida 6, sin generarlas dos veces).
                </span>
              </label>
            </div>
          )}
          <InstruccionesField
            value={instructions[salida.num] || ""}
            onChange={(v) => setInstructions((prev) => ({ ...prev, [salida.num]: v }))}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel de confirmación / edición de SEO (solo landing, salida 3)
// ---------------------------------------------------------------------------

function parseSeo(seoRaw) {
  if (!seoRaw) return null;
  try {
    const s = typeof seoRaw === "string" ? JSON.parse(seoRaw) : seoRaw;
    return {
      frase_clave: s.frase_clave || "",
      seo_title: s.seo_title || "",
      meta_description: s.meta_description || "",
      slug: s.slug || "",
      imagenes: Array.isArray(s.imagenes) ? s.imagenes : [],
      variant: (s.variant || "A").toUpperCase(),
      confirmed: !!s.confirmed,
      incluir_evaluador: !!s.incluir_evaluador,
    };
  } catch {
    return null;
  }
}

const VARIANT_OPTIONS = [
  { value: "A", label: "Variante A", hint: "Hero navy, secciones alternas crema y blanco" },
  { value: "B", label: "Variante B", hint: "Hero crema, importe en navy" },
];

function VariantSelector({ seoRaw, convocatoriaId }) {
  const { API, openConvocatoria } = useApp();
  const current = parseSeo(seoRaw)?.variant || "A";
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  async function pickVariant(v) {
    if (v === current || busy) return;
    setBusy(v);
    setError(null);
    try {
      const res = await fetch(`${API}/convocatorias/${convocatoriaId}/landing/variant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variante: v }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "No se pudo cambiar la variante.");
      }
      await openConvocatoria(convocatoriaId);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mb-3 p-3" style={{ border: "1px solid var(--color-navy-20)", background: "#f9fafb" }}>
      <span className="block text-xs font-semibold text-brand-blue uppercase tracking-wide mb-2">
        Variante de distribución
      </span>
      <div className="flex flex-wrap gap-2">
        {VARIANT_OPTIONS.map((opt) => {
          const active = opt.value === current;
          return (
            <button
              key={opt.value}
              onClick={() => pickVariant(opt.value)}
              disabled={!!busy}
              title={opt.hint}
              className={`text-xs px-3 py-1.5 border transition-colors disabled:opacity-50 ${
                active
                  ? "bg-brand-blue text-white border-brand-blue font-semibold"
                  : "bg-white text-brand-blue border-brand-blue/40 hover:border-brand-blue"
              }`}
              style={{ borderRadius: 0 }}
            >
              {busy === opt.value ? "Aplicando…" : opt.label}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-gray-500 mt-2">
        {VARIANT_OPTIONS.find((o) => o.value === current)?.hint}. Cambia solo la distribución de
        fondos; el contenido y el SEO no cambian.
      </p>
      {error && <p className="text-xs text-brand-red mt-1">{error}</p>}
    </div>
  );
}

function SeoPanel({ seoRaw, convocatoriaId }) {
  const { API, openConvocatoria } = useApp();
  const initial = parseSeo(seoRaw);

  // Alt sugerido (editable): borrador a partir de la frase clave para que el
  // consultor revise en vez de escribir de cero. Nunca pisa un alt ya guardado.
  const suggestAlt = (fraseClave, idx) => (fraseClave ? `${fraseClave} — imagen ${idx + 1}` : "");
  const initImgs = (arr, fraseClave) =>
    [0, 1].map((i) => ({
      url: arr?.[i]?.url || "",
      alt: arr?.[i]?.alt || suggestAlt(fraseClave, i),
    }));

  const [fraseClave, setFraseClave] = useState(initial?.frase_clave || "");
  const [title, setTitle] = useState(initial?.seo_title || "");
  const [meta, setMeta] = useState(initial?.meta_description || "");
  const [slug, setSlug] = useState(initial?.slug || "");
  const [imagenes, setImagenes] = useState(initImgs(initial?.imagenes, initial?.frase_clave));
  const [confirmed, setConfirmed] = useState(initial?.confirmed || false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState(null);

  // Re-sincronizar si cambia el SEO de origen (p. ej. tras regenerar la landing).
  useEffect(() => {
    const s = parseSeo(seoRaw);
    if (s) {
      setFraseClave(s.frase_clave);
      setTitle(s.seo_title);
      setMeta(s.meta_description);
      setSlug(s.slug);
      setImagenes(initImgs(s.imagenes, s.frase_clave));
      setConfirmed(s.confirmed);
    }
  }, [seoRaw]);

  function setImg(idx, key, value) {
    setImagenes((prev) => prev.map((img, i) => (i === idx ? { ...img, [key]: value } : img)));
  }

  if (!initial) return null;

  async function handleConfirm() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/convocatorias/${convocatoriaId}/landing/seo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seo_title: title,
          meta_description: meta,
          slug,
          frase_clave: fraseClave,
          imagenes: imagenes.filter((img) => img.url.trim()),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "No se pudo guardar el SEO.");
      }
      const data = await res.json();
      setConfirmed(true);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
      if (data.seo?.slug != null) setSlug(data.seo.slug);
      await openConvocatoria(convocatoriaId); // refresca el HTML/iframe con el nuevo título y meta
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const titleLen = title.length;
  const metaLen = meta.length;
  const inputCls =
    "w-full border text-sm px-3 py-2 bg-white text-gray-800 focus:outline-none focus:border-brand-blue";
  const inputStyle = { borderRadius: 0, borderColor: "var(--color-navy-20)" };

  return (
    <div
      className="mb-4 p-4"
      style={{
        border: confirmed ? "1px solid var(--color-navy-20)" : "2px solid var(--color-red)",
        background: confirmed ? "#f9fafb" : "#fff7f8",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-brand-blue uppercase tracking-wide">
          Campos SEO {confirmed ? "(confirmados)" : "— revisa y confirma"}
        </span>
        {confirmed ? (
          <span className="text-xs text-green-700 font-medium">✓ Confirmado</span>
        ) : (
          <span className="text-xs text-brand-red font-medium">Pendiente de confirmar</span>
        )}
      </div>

      <p className="text-xs text-gray-500 mb-3">
        Estos valores se copian manualmente en Yoast (WordPress) al publicar. El título y la meta
        description se incrustan en el HTML; el <strong>slug</strong> es independiente y no se inserta en el HTML.
      </p>

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Frase clave objetivo <span className="text-gray-400">(campo &quot;frase clave&quot; de Yoast — máx. 4 palabras, sin año)</span>
          </label>
          <input
            type="text"
            value={fraseClave}
            onChange={(e) => setFraseClave(e.target.value)}
            className={inputCls}
            style={inputStyle}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Título SEO{" "}
            <span className={titleLen > 60 ? "text-brand-red font-semibold" : "text-gray-400"}>
              ({titleLen}/60)
            </span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputCls}
            style={inputStyle}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Meta description{" "}
            <span className={metaLen > 142 ? "text-brand-red font-semibold" : "text-gray-400"}>
              ({metaLen}/142)
            </span>
          </label>
          <textarea
            value={meta}
            onChange={(e) => setMeta(e.target.value)}
            rows={2}
            className={inputCls}
            style={inputStyle}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Slug <span className="text-gray-400">(URL en WordPress — no va en el HTML)</span>
          </label>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className={inputCls}
            style={inputStyle}
          />
        </div>
      </div>

      {error && <p className="text-xs text-brand-red mt-2">{error}</p>}

      <div className="flex items-center gap-3 mt-3">
        <button
          onClick={handleConfirm}
          disabled={saving}
          className="text-xs px-4 py-2 bg-brand-blue text-white font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
          style={{ borderRadius: 0 }}
        >
          {saving ? "Guardando…" : confirmed ? "Guardar cambios" : "Confirmar SEO"}
        </button>
        {savedFlash && <span className="text-xs text-green-700">Guardado y aplicado al HTML.</span>}
      </div>

      <div className="mt-4" style={{ borderTop: "1px solid var(--color-navy-20)", paddingTop: "10px" }}>
        <span className="block text-xs font-semibold text-brand-blue uppercase tracking-wide mb-1">
          Imágenes de la landing
        </span>
        <p className="text-xs text-gray-500 mb-3">
          Sube 1-2 imágenes a la <strong>biblioteca de medios de WordPress</strong> y pega aquí su URL.
          El texto alt viene sugerido a partir de la frase clave — revísalo o cámbialo por algo más
          descriptivo de cada imagen antes de guardar.
        </p>
        <div className="space-y-3">
          {imagenes.map((img, idx) => (
            <div key={idx} className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Imagen {idx + 1} — URL (WordPress)
                </label>
                <input
                  type="text"
                  value={img.url}
                  onChange={(e) => setImg(idx, "url", e.target.value)}
                  placeholder="https://innovate40.es/wp-content/uploads/…"
                  className={inputCls}
                  style={inputStyle}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Texto alt (con la frase clave)
                </label>
                <input
                  type="text"
                  value={img.alt}
                  onChange={(e) => setImg(idx, "alt", e.target.value)}
                  className={inputCls}
                  style={inputStyle}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ítem de acordeón para entregables ya generados
// ---------------------------------------------------------------------------

function EntregableItem({
  salida, texto, instruccionPrevia, hasJsonData, seoRaw, convocatoriaId, isOpen, onToggle,
  onRegenerate, outputStatus, output4Progress, costEur,
}) {
  const { API } = useApp();
  const [copied, setCopied] = useState(false);
  const [downloadingJson, setDownloadingJson] = useState(false);
  const [showRegenPanel, setShowRegenPanel] = useState(false);
  const [regenInstr, setRegenInstr] = useState(instruccionPrevia || "");
  const seoInicial = parseSeo(seoRaw);
  const [regenModo, setRegenModo] = useState("ABIERTA");
  const [regenVariant, setRegenVariant] = useState(seoInicial?.variant || "A");
  const [regenIncluirEvaluador, setRegenIncluirEvaluador] = useState(seoInicial?.incluir_evaluador || false);

  function handleCopy(e) {
    e.stopPropagation();
    navigator.clipboard.writeText(texto);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload(e) {
    e.stopPropagation();
    downloadFile(
      texto,
      `salida_${salida.num}_${salida.label.replace(/\s+/g, "_")}.${salida.ext}`
    );
  }

  function handlePreview(e) {
    e.stopPropagation();
    const blob = new Blob([texto], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 10000);
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
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json;charset=utf-8",
      });
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

  let loadingMsg = "Generando...";
  if (outputStatus === "queued") loadingMsg = "En cola...";
  else if (outputStatus === "running" && salida.num === 4 && output4Progress) {
    loadingMsg = output4Progress.actual === 0
      ? "Identificando apartados..."
      : `Apartado ${output4Progress.actual} de ${output4Progress.total}`;
  }

  // Button base
  const btnBase = "text-xs px-2.5 py-1 border transition-colors font-medium";
  // When accordion is open (navy bg) — white outline buttons
  const btnOpen   = "border-white/40 text-white hover:bg-white hover:text-brand-blue";
  // When accordion is closed — navy outline per brand spec (secondary buttons)
  const btnClosed = "border-brand-blue text-brand-blue bg-transparent hover:bg-brand-blue hover:text-white";

  return (
    <div className={`border-b border-gray-100 last:border-b-0 ${isOpen ? "bg-white" : ""}`}>
      <div
        onClick={onToggle}
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer select-none transition-colors ${
          isOpen ? "bg-brand-blue" : "bg-white hover:bg-gray-50"
        }`}
      >
        {/* Número */}
        <span
          className={`font-slab font-bold text-sm w-5 shrink-0 ${
            isOpen ? "text-brand-red" : "text-brand-red"
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

        {/* Acciones */}
        <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
          {/* Coste */}
          {costEur != null && !isRegenerating && (
            <span className={`text-xs ${isOpen ? "text-white/40" : "text-gray-400"}`}>
              {costEur < 0.01 ? "<0.01 €" : `${costEur.toFixed(3)} €`}
            </span>
          )}

          {!salida.isHtml && (
            <button onClick={handleCopy} className={`${btnBase} ${isOpen ? btnOpen : btnClosed}`}>
              {copied ? "¡Copiado!" : "Copiar"}
            </button>
          )}
          <button onClick={handleDownload} className={`${btnBase} ${isOpen ? btnOpen : btnClosed}`}>
            .{salida.ext}
          </button>
          {salida.isHtml && (
            <button onClick={handlePreview} className={`${btnBase} ${isOpen ? btnOpen : btnClosed}`}>
              Vista previa
            </button>
          )}
          {salida.hasJson && hasJsonData && (
            <button
              onClick={handleDownloadJson}
              disabled={downloadingJson}
              className={`${btnBase} disabled:opacity-40 ${isOpen ? btnOpen : btnClosed}`}
            >
              {downloadingJson ? <Spinner className="w-3 h-3" /> : ".json"}
            </button>
          )}

          {isRegenerating ? (
            <span className={`flex items-center gap-1.5 text-xs ${isOpen ? "text-white" : "text-brand-red"}`}>
              <Spinner className="w-3 h-3" />
              <span className="whitespace-nowrap">{loadingMsg}</span>
            </span>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); setShowRegenPanel((v) => !v); }}
              className={`${btnBase} border-brand-red text-brand-red hover:bg-brand-red hover:text-white ${
                isOpen ? "border-brand-red/70 text-white/80 hover:bg-brand-red hover:border-brand-red hover:text-white" : ""
              }`}
            >
              Regenerar
            </button>
          )}
        </div>

        <span className={`text-xs shrink-0 ml-1 ${isOpen ? "text-white/60" : "text-gray-400"}`}>
          {isOpen ? "▲" : "▼"}
        </span>
      </div>

      {showRegenPanel && !isRegenerating && (
        <div
          className="px-5 py-4 flex flex-col gap-2"
          style={{ borderTop: "1px solid var(--color-navy-20)", background: "#f9f9f9" }}
          onClick={(e) => e.stopPropagation()}
        >
          {salida.num === 3 && (
            <div className="flex flex-col gap-1.5 mb-1">
              <span className="text-xs font-semibold text-brand-blue uppercase tracking-wide">
                Modo de generación
              </span>
              <div className="flex flex-col gap-1">
                {[
                  { value: "ABIERTA",    label: "Convocatoria abierta o inminente" },
                  { value: "ANTICIPADA", label: "Posicionamiento anticipado (edición futura)" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 cursor-pointer text-xs text-gray-700">
                    <input
                      type="radio"
                      name={`regenModo3-${salida.num}`}
                      value={opt.value}
                      checked={regenModo === opt.value}
                      onChange={() => setRegenModo(opt.value)}
                      style={{ accentColor: "var(--color-navy)" }}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
              <span className="text-xs font-semibold text-brand-blue uppercase tracking-wide mt-1">
                Variante de distribución
              </span>
              <div className="flex flex-wrap gap-2">
                {VARIANT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setRegenVariant(opt.value)}
                    title={opt.hint}
                    className={`text-xs px-3 py-1.5 border transition-colors ${
                      regenVariant === opt.value
                        ? "bg-brand-blue text-white border-brand-blue font-semibold"
                        : "bg-white text-brand-blue border-brand-blue/40 hover:border-brand-blue"
                    }`}
                    style={{ borderRadius: 0 }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <label className="flex items-start gap-2 cursor-pointer text-xs text-gray-700 mt-2">
                <input
                  type="checkbox"
                  checked={regenIncluirEvaluador}
                  onChange={(e) => setRegenIncluirEvaluador(e.target.checked)}
                  className="w-4 h-4 shrink-0 mt-0.5"
                  style={{ accentColor: "var(--color-navy)" }}
                />
                <span>
                  Incluir el evaluador de encaje embebido en la landing (comparte las mismas
                  preguntas que la salida 6, sin generarlas dos veces).
                </span>
              </label>
            </div>
          )}
          <label className="text-xs font-semibold text-brand-blue uppercase tracking-wide">
            Instrucción adicional{" "}
            <span className="font-normal normal-case text-gray-400">(opcional)</span>
          </label>
          <textarea
            value={regenInstr}
            onChange={(e) => setRegenInstr(e.target.value)}
            placeholder={INSTR_PLACEHOLDER}
            rows={2}
            className="textarea-brand"
          />
          <div className="flex gap-2 mt-1">
            <button
              onClick={() => {
                setShowRegenPanel(false);
                onRegenerate(
                  regenInstr,
                  salida.num === 3
                    ? { modo: regenModo, variante: regenVariant, incluir_evaluador: regenIncluirEvaluador }
                    : undefined
                );
              }}
              className="text-xs px-3 py-1.5 bg-brand-red text-white font-semibold hover:bg-red-800 transition-colors"
            >
              Confirmar regeneración
            </button>
            <button
              onClick={() => setShowRegenPanel(false)}
              className="text-xs px-3 py-1.5 border border-gray-300 text-gray-500 hover:border-gray-500 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {isOpen && (
        <div className="px-5 py-5" style={{ borderTop: "1px solid var(--color-navy-20)" }}>
          {salida.isHtml ? (
            <div className="space-y-3">
              {salida.num === 3 && seoRaw && (
                <>
                  <VariantSelector seoRaw={seoRaw} convocatoriaId={convocatoriaId} />
                  <SeoPanel seoRaw={seoRaw} convocatoriaId={convocatoriaId} />
                </>
              )}
              <iframe
                srcDoc={texto}
                title={salida.label}
                style={{ width: "100%", height: "680px", border: "1px solid #e5e7eb" }}
                sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
              />
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={handleDownload}
                  className="text-xs px-3 py-1.5 bg-brand-blue text-white font-medium hover:bg-navy-dark transition-colors"
                >
                  Descargar .html
                </button>
                <button
                  onClick={handlePreview}
                  className="text-xs px-3 py-1.5 border border-brand-blue text-brand-blue font-medium hover:bg-brand-blue hover:text-white transition-colors"
                >
                  Abrir en el navegador
                </button>
              </div>
            </div>
          ) : (
            <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed">
              {texto}
            </pre>
          )}
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
  const [outputStatuses, setOutputStatuses] = useState({});
  const [output4Progress, setOutput4Progress] = useState(null);
  const [error, setError] = useState(null);

  const [instructions, setInstructions] = useState({});
  const [mode3, setMode3] = useState("ABIERTA");
  const [variant3, setVariant3] = useState("A");
  const [incluirEvaluador3, setIncluirEvaluador3] = useState(false);

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

      setOutputStatuses(progress?.outputs || {});
      setOutput4Progress(progress?.output4_progress || null);

      if (status === "completed" || status === "error") {
        stopPolling();
        setSelected([]);
        if (types.length === 1 && status === "completed") setOpenNum(types[0]);
        if (status === "error") {
          const outputErrors = Object.entries(progress?.outputs || {})
            .filter(([, v]) => v.status === "error")
            .map(([k, v]) => `Salida ${k}: ${v.error || "error desconocido"}`)
            .join(" | ");
          const topError = progress?.error || "";
          setError(outputErrors || topError || "Ha ocurrido un error durante la generación.");
        }
        await openConvocatoria(convocatoria.id);
      } else if (status === "running") {
        await openConvocatoria(convocatoria.id);
      }
    } catch {
      // transient network error — keep polling
    }
  }

  async function generate(types, overrideInstructions, output3Opts) {
    stopPolling();
    setError(null);
    setOutput4Progress(null);

    const instrMap = overrideInstructions != null ? overrideInstructions : instructions;
    const initialStatuses = {};
    types.forEach((t) => { initialStatuses[String(t)] = { status: "queued" }; });
    setOutputStatuses(initialStatuses);

    const salidas = types.map((t) => ({
      output_type: t,
      instrucciones_adicionales: instrMap[t] || "",
      ...(t === 3 ? {
        modo: output3Opts?.modo ?? mode3,
        variante: output3Opts?.variante ?? variant3,
        incluir_evaluador: output3Opts?.incluir_evaluador ?? incluirEvaluador3,
      } : {}),
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
      await pollJob(job_id, types);
      pollRef.current = setInterval(() => pollJob(job_id, types), 2000);
    } catch (err) {
      setError(err.message);
      setOutputStatuses({});
    }
  }

  const pendientes = SALIDAS.filter((s) => !entregables[String(s.num)]);
  const generadas  = SALIDAS.filter((s) =>  entregables[String(s.num)]);

  return (
    <div>
      {error && (
        <div className="bg-brand-red text-white text-sm px-4 py-3 mb-4">{error}</div>
      )}

      {/* Pendientes */}
      {pendientes.length > 0 && (
        <section className="mb-8">
          <h3 className="text-xs font-semibold text-brand-blue uppercase tracking-wide mb-4">
            Generar entregables
          </h3>
          <div
            className="mb-5 divide-y"
            style={{ borderColor: "var(--color-navy-20)" }}
          >
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
                mode3={mode3}
                setMode3={setMode3}
                variant3={variant3}
                setVariant3={setVariant3}
                incluirEvaluador3={incluirEvaluador3}
                setIncluirEvaluador3={setIncluirEvaluador3}
              />
            ))}
          </div>
          <button
            onClick={() => generate(selected)}
            disabled={selected.length === 0 || isAnyRunning()}
            className="btn-primary bg-brand-blue text-white text-sm font-semibold px-5 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Generar seleccionados
          </button>
        </section>
      )}

      {/* Generadas */}
      {generadas.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-brand-blue uppercase tracking-wide mb-4">
            Entregables generados
          </h3>
          <div style={{ border: "1px solid var(--color-navy-20)" }}>
            {generadas.map((s) => {
              const salStatus = outputStatuses[String(s.num)];
              return (
                <EntregableItem
                  key={`${convocatoria.id}-${s.num}`}
                  salida={s}
                  texto={entregables[String(s.num)]}
                  instruccionPrevia={entregables[`${s.num}_instruccion`] || ""}
                  hasJsonData={!!entregables[`${s.num}_json`]}
                  seoRaw={entregables[`${s.num}_seo`] || ""}
                  convocatoriaId={convocatoria.id}
                  isOpen={openNum === s.num}
                  onToggle={() => toggleAccordion(s.num)}
                  outputStatus={salStatus?.status}
                  output4Progress={s.num === 4 ? output4Progress : null}
                  costEur={salStatus?.cost_eur ?? null}
                  onRegenerate={(instr, output3Opts) => generate([s.num], { [s.num]: instr }, output3Opts)}
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
