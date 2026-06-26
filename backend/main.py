"""
ConvoKit backend — FastAPI application entry point.

Los endpoints de negocio (convocatorias, subida de documentos, generación)
se añaden paso a paso según el orden de implementación definido en CLAUDE.md.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()
from typing import Annotated

import anthropic
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db
import extractors
import prompts as p


class ConvocatoriaCreate(BaseModel):
    nombre: str


class GenerateRequest(BaseModel):
    output_types: list[int]


def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="La clave de la API de Claude no está configurada en el servidor.",
        )
    return anthropic.Anthropic(api_key=api_key)


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
def create_convocatoria(body: ConvocatoriaCreate):
    """
    Crea una nueva convocatoria. Recibe {"nombre": "..."} y devuelve el id
    asignado automáticamente por SQLite.
    """
    if not body.nombre.strip():
        raise HTTPException(status_code=422, detail="El nombre de la convocatoria no puede estar vacío.")
    convocatoria_id = db.create_convocatoria(body.nombre.strip())
    return {"id": convocatoria_id, "nombre": body.nombre.strip()}


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


# ---------------------------------------------------------------------------
# Generación de entregables con Claude API
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate")
def generate_outputs(convocatoria_id: int, body: GenerateRequest):
    """
    Genera uno o varios entregables para una convocatoria.

    Recibe {"output_types": [1]} con los números de salida a generar (1-7).
    Llama a Claude API con el system prompt específico de cada salida y el
    contexto extraído de los documentos. Guarda los resultados en SQLite y
    los devuelve en la respuesta.

    Solo la Salida 1 está implementada en el Paso 5. Las salidas 2-7 se
    añaden en el Paso 8.
    """
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    if not conv["documentos_json"]:
        raise HTTPException(
            status_code=422,
            detail="Esta convocatoria no tiene documentos. Sube los archivos antes de generar entregables.",
        )

    valid_types = set(p.SYSTEM_PROMPTS.keys())
    requested = set(body.output_types)
    unknown = requested - set(range(1, 8))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}. Usa números del 1 al 7.",
        )
    not_implemented = requested - valid_types
    if not_implemented:
        raise HTTPException(
            status_code=422,
            detail=f"Las salidas {sorted(not_implemented)} aún no están implementadas.",
        )

    context = extractors.build_context(conv["documentos_json"])
    client = _get_anthropic_client()
    generated = {}

    for output_type in sorted(requested):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=p.MAX_TOKENS[output_type],
                system=p.SYSTEM_PROMPTS[output_type],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"A continuación tienes los documentos de la convocatoria "
                            f"'{conv['nombre']}'.\n\n{context}"
                        ),
                    }
                ],
                timeout=180,
            )
            generated[str(output_type)] = response.content[0].text
        except anthropic.APITimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"La generación de la salida {output_type} superó el tiempo límite. Inténtalo de nuevo.",
            )
        except anthropic.APIError:
            raise HTTPException(
                status_code=502,
                detail=f"Error al comunicarse con la API de Claude al generar la salida {output_type}. Inténtalo de nuevo.",
            )

    db.update_entregables(convocatoria_id, generated)

    return {
        "convocatoria_id": convocatoria_id,
        "generados": list(generated.keys()),
        "entregables": generated,
    }
