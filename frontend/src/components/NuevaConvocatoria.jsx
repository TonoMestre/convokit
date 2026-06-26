import { useRef, useState } from "react";
import { useApp } from "../context/AppContext";

const ETIQUETAS = [
  { value: "bases_reguladoras", label: "Bases reguladoras" },
  { value: "convocatoria", label: "Convocatoria del ejercicio" },
  { value: "plantilla_memoria", label: "Plantilla de memoria / solicitud" },
  { value: "resolucion_anterior", label: "Resolución de ejercicio anterior" },
  { value: "anexo", label: "Anexo o documento complementario" },
];

const ACCEPT = ".pdf,.docx,.xlsx,.txt";

export default function NuevaConvocatoria() {
  const { API, loadConvocatorias, openConvocatoria, setActiveConvocatoria } = useApp();
  const fileInputRef = useRef(null);

  const [nombre, setNombre] = useState("");
  const [archivos, setArchivos] = useState([]); // [{ file, etiqueta }]
  const [step, setStep] = useState("form"); // "form" | "procesando" | "listo"
  const [convId, setConvId] = useState(null);
  const [processingMsg, setProcessingMsg] = useState("");
  const [error, setError] = useState(null);

  function handleFiles(fileList) {
    const nuevos = Array.from(fileList).map((file) => ({
      file,
      etiqueta: "bases_reguladoras",
    }));
    setArchivos((prev) => [...prev, ...nuevos]);
  }

  function handleDrop(e) {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  }

  function removeArchivo(index) {
    setArchivos((prev) => prev.filter((_, i) => i !== index));
  }

  function updateEtiqueta(index, value) {
    setArchivos((prev) =>
      prev.map((a, i) => (i === index ? { ...a, etiqueta: value } : a))
    );
  }

  async function handleProcesar() {
    if (!nombre.trim()) { setError("Introduce el nombre de la convocatoria."); return; }
    if (archivos.length === 0) { setError("Añade al menos un archivo."); return; }
    setError(null);
    setStep("procesando");
    setProcessingMsg("Creando convocatoria...");

    try {
      // 1. Crear convocatoria
      const resConv = await fetch(`${API}/convocatorias`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: nombre.trim() }),
      });
      if (!resConv.ok) throw new Error((await resConv.json()).detail);
      const conv = await resConv.json();
      setConvId(conv.id);

      // 2. Subir archivos
      setProcessingMsg("Extrayendo texto de los documentos...");
      const formData = new FormData();
      archivos.forEach(({ file, etiqueta }) => {
        formData.append("files", file);
        formData.append("etiquetas", etiqueta);
      });
      const resUp = await fetch(`${API}/convocatorias/${conv.id}/upload`, {
        method: "POST",
        body: formData,
      });
      if (!resUp.ok) throw new Error((await resUp.json()).detail);

      await loadConvocatorias();
      await openConvocatoria(conv.id);
      setStep("listo");
    } catch (err) {
      setError(err.message || "Error al procesar los documentos.");
      setStep("form");
    }
  }

  if (step === "procesando") {
    return (
      <div className="flex flex-col items-center justify-center h-full text-brand-blue font-sans">
        <div className="text-4xl mb-4 animate-spin">⟳</div>
        <p className="text-lg font-medium">{processingMsg}</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-10 px-6 font-sans">
      <h2 className="font-slab text-2xl font-bold text-brand-blue mb-6">Nueva convocatoria</h2>

      {error && (
        <div className="bg-brand-red text-white text-sm px-4 py-3 mb-5">
          {error}
        </div>
      )}

      {/* Nombre */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-brand-blue mb-1">
          Nombre de la convocatoria <span className="text-brand-red">*</span>
        </label>
        <input
          type="text"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Ej. INPYME 2026"
          className="w-full border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-brand-blue"
        />
      </div>

      {/* Zona de carga */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-brand-blue mb-2">
          Documentos de la convocatoria
        </label>
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileInputRef.current.click()}
          className="border-2 border-dashed border-gray-300 hover:border-brand-blue cursor-pointer py-8 text-center transition-colors"
        >
          <p className="text-sm text-gray-500">
            Arrastra archivos aquí o <span className="text-brand-blue font-semibold">haz clic para seleccionar</span>
          </p>
          <p className="text-xs text-gray-400 mt-1">PDF, DOCX, XLSX, TXT — sin límite de archivos</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Lista de archivos */}
      {archivos.length > 0 && (
        <div className="mb-6 space-y-2">
          {archivos.map(({ file, etiqueta }, index) => (
            <div key={index} className="flex items-center gap-3 border border-gray-200 px-3 py-2 text-sm">
              <span className="flex-1 truncate text-gray-700 font-medium">{file.name}</span>
              <select
                value={etiqueta}
                onChange={(e) => updateEtiqueta(index, e.target.value)}
                className="border border-gray-300 text-xs px-2 py-1 bg-white focus:outline-none focus:border-brand-blue"
              >
                {ETIQUETAS.map((et) => (
                  <option key={et.value} value={et.value}>{et.label}</option>
                ))}
              </select>
              <button
                onClick={() => removeArchivo(index)}
                className="text-gray-400 hover:text-brand-red font-bold text-base leading-none"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Botón procesar */}
      <button
        onClick={handleProcesar}
        disabled={archivos.length === 0 || !nombre.trim()}
        className="bg-brand-blue text-white text-sm font-semibold px-6 py-2.5 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
      >
        Procesar documentos
      </button>
    </div>
  );
}
