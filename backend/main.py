"""
ConvoKit backend — FastAPI application entry point.

Los endpoints de negocio (convocatorias, subida de documentos, generación)
se añaden paso a paso según el orden de implementación definido en CLAUDE.md.
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import database as db
import extractors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar la aplicación."""
    db.init_db()
    yield


app = FastAPI(title="ConvoKit API", lifespan=lifespan)

# CORS abierto durante el MVP (uso interno, sin autenticación).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Convocatorias — CRUD básico
# ---------------------------------------------------------------------------

@app.post("/convocatorias", status_code=201)
def create_convocatoria(nombre: Annotated[str, Form()]):
    """
    Crea una nueva convocatoria con el nombre indicado.
    Devuelve el id asignado.
    """
    if not nombre.strip():
        raise HTTPException(status_code=422, detail="El nombre de la convocatoria no puede estar vacío.")
    convocatoria_id = db.create_convocatoria(nombre.strip())
    return {"id": convocatoria_id, "nombre": nombre.strip()}


@app.get("/convocatorias")
def list_convocatorias():
    """Lista todas las convocatorias ordenadas por fecha descendente."""
    return db.list_convocatorias()


@app.get("/convocatorias/{convocatoria_id}")
def get_convocatoria(convocatoria_id: int):
    """Devuelve el detalle completo de una convocatoria: documentos y entregables."""
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    return conv


@app.delete("/convocatorias/{convocatoria_id}", status_code=204)
def delete_convocatoria(convocatoria_id: int):
    """Elimina una convocatoria y todos sus datos."""
    deleted = db.delete_convocatoria(convocatoria_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")


# ---------------------------------------------------------------------------
# Subida de documentos y extracción de texto
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/upload")
async def upload_documents(
    convocatoria_id: int,
    files: Annotated[list[UploadFile], File(description="Archivos a subir (PDF, TXT en este paso)")],
    etiquetas: Annotated[list[str], Form(description="Etiqueta por cada archivo en el mismo orden")],
):
    """
    Sube uno o varios archivos a una convocatoria existente, extrae el texto
    y guarda el contexto compuesto en SQLite.

    Cada archivo debe tener su etiqueta correspondiente en el mismo índice:
    - bases_reguladoras
    - convocatoria
    - plantilla_memoria
    - resolucion_anterior
    - anexo

    Paso 3: admite PDF y TXT. DOCX y XLSX se añaden en el Paso 4.
    """
    if db.get_convocatoria(convocatoria_id) is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    if len(files) != len(etiquetas):
        raise HTTPException(
            status_code=422,
            detail="El número de archivos y etiquetas debe coincidir.",
        )

    valid_labels = set(extractors.LABEL_HEADERS.keys())
    documents = []
    errors = []

    for file, etiqueta in zip(files, etiquetas):
        if etiqueta not in valid_labels:
            errors.append(
                f"'{file.filename}': etiqueta '{etiqueta}' no válida. "
                f"Usa una de: {', '.join(valid_labels)}."
            )
            continue

        content = await file.read()

        try:
            texto = extractors.extract_text(content, file.filename)
        except ValueError as exc:
            errors.append(f"'{file.filename}': {exc}")
            continue

        documents.append(
            {
                "etiqueta": etiqueta,
                "nombre_archivo": file.filename,
                "texto": texto,
            }
        )

    if errors and not documents:
        # Todos los archivos fallaron: devolver error completo.
        raise HTTPException(status_code=422, detail=errors)

    # Guardar documentos en SQLite y construir contexto compuesto.
    db.update_documentos(convocatoria_id, documents)
    context = extractors.build_context(documents)

    response: dict = {
        "convocatoria_id": convocatoria_id,
        "documentos_procesados": len(documents),
        "palabras_en_contexto": len(context.split()),
        "documentos": [
            {"nombre_archivo": d["nombre_archivo"], "etiqueta": d["etiqueta"]}
            for d in documents
        ],
    }

    if errors:
        response["advertencias"] = errors

    return response
