import { useRef, useState } from "react";
import { useApp } from "../context/AppContext";
import EntregablePanel from "./EntregablePanel";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const LABEL_DISPLAY = {
  bases_reguladoras: "Bases reguladoras",
  convocatoria: "Convocatoria del ejercicio",
  plantilla_memoria: "Plantilla de memoria",
  resolucion_anterior: "Resolución anterior",
  anexo: "Anexo",
  correccion: "Corrección / Rectificación",
  guia_convocante: "Guía del convocante",
  adenda: "Adenda",
};

const ADDITIONAL_LABEL_OPTIONS = [
  { value: "correccion", label: "Corrección / Rectificación" },
  { value: "guia_convocante", label: "Guía del convocante" },
  { value: "adenda", label: "Adenda" },
  { value: "__otro__", label: "Otro (texto libre)" },
];

export default function DetalleConvocatoria() {
  const { activeConvocatoria, setActiveConvocatoria, deleteConvocatoria } = useApp();

  const [showAddForm, setShowAddForm] = useState(false);
  const [addFiles, setAddFiles] = useState([]);
  const [addLabel, setAddLabel] = useState("correccion");
  const [customLabel, setCustomLabel] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  if (!activeConvocatoria) return null;

  const docs = activeConvocatoria.documentos_json ?? [];
  const originalDocs = docs.filter((d) => !d.es_adicional);
  const additionalDocs = docs.filter((d) => d.es_adicional);

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

  function getEffectiveLabel() {
    return addLabel === "__otro__" ? customLabel.trim() : addLabel;
  }

  async function handleAddDocuments(e) {
    e.preventDefault();
    const effectiveLabel = getEffectiveLabel();
    if (!effectiveLabel) {
      setUploadError("Escribe un nombre para el tipo de documento.");
      return;
    }
    if (addFiles.length === 0) {
      setUploadError("Selecciona al menos un archivo.");
      return;
    }

    setUploading(true);
    setUploadError(null);

    const form = new FormData();
    for (const f of addFiles) {
      form.append("files", f);
      form.append("etiquetas", effectiveLabel);
    }

    try {
      const res = await fetch(`${API}/convocatorias/${activeConvocatoria.id}/documentos/add`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Error al subir los documentos.");
      }
      const updated = await fetch(`${API}/convocatorias/${activeConvocatoria.id}`).then((r) => r.json());
      setActiveConvocatoria(updated);
      setShowAddForm(false);
      setAddFiles([]);
      setAddLabel("correccion");
      setCustomLabel("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  }

  function labelBadge(d) {
    const display = LABEL_DISPLAY[d.etiqueta] ?? d.etiqueta;
    if (d.es_adicional) {
      return (
        <span
          className="text-xs px-2 py-0.5"
          style={{ background: "#fef3c7", color: "#92400e", border: "1px solid #fcd34d" }}
        >
          {display}
        </span>
      );
    }
    return (
      <span className="text-xs text-brand-blue/60 px-2 py-0.5" style={{ background: "var(--color-navy-20)" }}>
        {display}
      </span>
    );
  }

  const allDocs = [...originalDocs, ...additionalDocs];

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
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-brand-blue uppercase tracking-wide">
            Documentos procesados
          </h3>
          <button
            onClick={() => { setShowAddForm((v) => !v); setUploadError(null); }}
            className="text-xs text-brand-blue hover:text-brand-red transition-colors underline"
          >
            {showAddForm ? "Cancelar" : "+ Añadir documento"}
          </button>
        </div>

        {allDocs.length === 0 ? (
          <p className="text-sm text-gray-400">Sin documentos.</p>
        ) : (
          <ul className="space-y-1 mb-4">
            {allDocs.map((d, i) => (
              <li key={i} className="flex items-center gap-3 text-sm py-1.5" style={{ borderBottom: "1px solid var(--color-navy-20)" }}>
                <span className="font-medium text-gray-700 flex-1 truncate">{d.nombre_archivo}</span>
                {labelBadge(d)}
                {d.es_adicional && (
                  <span className="text-xs text-amber-600 font-medium">ADICIONAL</span>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Formulario de documentos adicionales */}
        {showAddForm && (
          <form onSubmit={handleAddDocuments} className="border border-brand-blue/20 p-4 mt-2" style={{ background: "#f9fafb" }}>
            <p className="text-sm font-semibold text-brand-blue mb-3">Añadir documento adicional</p>

            <div className="mb-3">
              <label className="block text-xs text-gray-600 mb-1">Tipo de documento</label>
              <select
                value={addLabel}
                onChange={(e) => setAddLabel(e.target.value)}
                className="w-full border border-gray-300 text-sm px-3 py-2 bg-white"
                style={{ borderRadius: 0 }}
              >
                {ADDITIONAL_LABEL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {addLabel === "__otro__" && (
              <div className="mb-3">
                <label className="block text-xs text-gray-600 mb-1">Nombre del tipo (texto libre)</label>
                <input
                  type="text"
                  value={customLabel}
                  onChange={(e) => setCustomLabel(e.target.value)}
                  placeholder="Ej: Resolución de ampliación de plazo"
                  className="w-full border border-gray-300 text-sm px-3 py-2"
                  style={{ borderRadius: 0 }}
                />
              </div>
            )}

            <div className="mb-3">
              <label className="block text-xs text-gray-600 mb-1">Archivo(s)</label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.txt"
                onChange={(e) => setAddFiles(Array.from(e.target.files))}
                className="text-sm"
              />
            </div>

            {uploadError && (
              <p className="text-xs text-brand-red mb-3">{uploadError}</p>
            )}

            <button
              type="submit"
              disabled={uploading}
              className="bg-brand-blue text-white text-sm px-4 py-2 hover:opacity-90 transition-opacity disabled:opacity-50"
              style={{ borderRadius: 0 }}
            >
              {uploading ? "Subiendo…" : "Subir documento"}
            </button>
          </form>
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
