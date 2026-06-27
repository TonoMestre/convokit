"""
ConvoKit backend — FastAPI application entry point.
"""

import json
import os
from contextlib import asynccontextmanager
from typing import Annotated

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

import database as db
import exporters
import extractors
import prompts as p


class ConvocatoriaCreate(BaseModel):
    nombre: str


class SalidaRequest(BaseModel):
    output_type: int
    instrucciones_adicionales: str = ""
    modo: str | None = None  # Solo para salida 3: "ABIERTA" o "ANTICIPADA"


class GenerateRequest(BaseModel):
    salidas: list[SalidaRequest]


def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="La clave de la API de Claude no está configurada en el servidor.",
        )
    return anthropic.Anthropic(api_key=api_key)


def _claude(client: anthropic.Anthropic, system: str, user: str, max_tokens: int = 2000) -> str:
    """Wrapper de llamada síncrona a Claude con timeout uniforme."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=180,
    )
    return response.content[0].text


def _strip_fences(text: str) -> str:
    """Elimina bloques de código markdown que Claude a veces añade alrededor del JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    return text.strip()


def _parse_json(text: str) -> object:
    """Parsea JSON de la respuesta de Claude, tolerando bloques de código."""
    return json.loads(_strip_fences(text))


def _generate_output_4(client: anthropic.Anthropic, conv_name: str, context: str,
                        instrucciones: str = "") -> tuple[str, list[dict]]:
    """
    Generación multi-llamada de la salida 4 (set de prompts para la memoria).

    Flujo:
    1. Una llamada para extraer la lista de secciones de la memoria.
    2. Una llamada por sección para generar su prompt individual.
    3. Concatenación de todos los bloques en un único markdown.

    Retorna (markdown_completo, array_json_secciones).
    """
    # Paso 1: extraer secciones
    raw_sections = _claude(
        client,
        system=p.SECTION_EXTRACTOR_PROMPT,
        user=f"Documentos de la convocatoria '{conv_name}':\n\n{context}",
        max_tokens=1500,
    )
    try:
        secciones = _parse_json(raw_sections).get("secciones", [])
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudieron identificar los apartados de la memoria. Comprueba que has subido la plantilla de memoria.",
        )

    if not secciones:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron apartados en la plantilla de memoria.",
        )

    # Paso 2: generar markdown por sección
    header = (
        f"# Set de prompts para la memoria — {conv_name}\n\n"
        "> **Nota de uso:** El **Perfil Estratégico de Empresa** (documento de Ruta i40) "
        "es la fuente principal de información sobre la empresa. Tenlo abierto antes de usar "
        "estos prompts: cubre historia, actividad, datos económicos, estructura accionarial, "
        "mercados y experiencia previa. Cada prompt indica únicamente la documentación "
        "ADICIONAL específica del proyecto que el Perfil no cubre.\n\n---"
    )
    markdown_parts = [header]

    for seccion in secciones:
        user_msg = (
            f"Convocatoria: {conv_name}\n"
            f"Apartado: {seccion['codigo']} — {seccion['nombre']} "
            f"(puntos_max: {seccion.get('puntos_max') or 'no especificado'}, "
            f"habilitante: {seccion.get('es_habilitante', False)})\n\n"
            f"Documentos de la convocatoria:\n{context}"
        )
        if instrucciones.strip():
            user_msg += f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
        raw_section = _claude(client, system=p.SECTION_PROMPT_SYSTEM, user=user_msg, max_tokens=2000)
        markdown_parts.append(raw_section)

    markdown = "\n\n---\n\n".join(markdown_parts)

    # Paso 3: extraer JSON estructurado del markdown completo en una sola llamada.
    raw_json = _claude(
        client,
        system=p.OUTPUT_4_JSON_EXTRACTOR,
        user=markdown,
        max_tokens=8192,
    )
    try:
        json_sections = _parse_json(raw_json)
        if not isinstance(json_sections, list):
            json_sections = []
    except Exception:
        json_sections = []

    return markdown, json_sections


def _build_user_prompt(conv_name: str, context: str, output_type: int,
                        instrucciones: str = "", modo: str = "ABIERTA") -> str:
    """Construye el user message para Claude según el tipo de salida."""
    instr_block = (
        f"\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
        if instrucciones.strip() else ""
    )
    if output_type == 3:
        modo_label = (modo or "ABIERTA").upper()
        if modo_label == "ANTICIPADA":
            modo_block = (
                "*** MODO DE GENERACIÓN OBLIGATORIO: ANTICIPADA ***\n"
                "Esta landing se genera para posicionamiento anticipado de una convocatoria futura aún no publicada. "
                "Los documentos aportados son de una edición anterior y sirven exclusivamente como referencia histórica. "
                "DEBES redactar en condicional: usa 'se espera', 'en línea con ediciones anteriores', 'habitualmente'. "
                "No afirmes NINGÚN importe, porcentaje ni plazo como cifra confirmada para la próxima edición. "
                "Menciona el descuento por contratación anticipada de Ruta por convocatoria, sin indicar el porcentaje."
            )
        else:
            modo_block = (
                "MODO DE GENERACIÓN: ABIERTA\n"
                "Usa los datos confirmados de los documentos aportados: importes, porcentajes, plazos, presupuesto total."
            )
        return (
            f"{modo_block}"
            f"{instr_block}\n\n"
            f"Documentos de la convocatoria '{conv_name}':\n\n{context}\n\n"
            f"Genera la landing page siguiendo las instrucciones del system prompt."
        )
    else:
        return (
            f"A continuación tienes los documentos de la convocatoria procesados:\n\n{context}"
            f"{instr_block}\n\n"
            f"Genera el entregable siguiendo las instrucciones del system prompt."
        )


def _generate_output_5_json(client: anthropic.Anthropic, md_text: str) -> list[dict]:
    """Convierte el markdown de la salida 5 al array JSON del PRD sección 12.2."""
    raw = _claude(
        client,
        system=p.OUTPUT_5_JSON_CONVERTER,
        user=f"Convierte la siguiente lista de documentación a JSON:\n\n{md_text}",
        max_tokens=3000,
    )
    try:
        return _parse_json(raw)
    except Exception:
        return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="ConvoKit API", lifespan=lifespan)

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
    if not body.nombre.strip():
        raise HTTPException(status_code=422, detail="El nombre de la convocatoria no puede estar vacío.")
    convocatoria_id = db.create_convocatoria(body.nombre.strip())
    return {"id": convocatoria_id, "nombre": body.nombre.strip()}


@app.get("/convocatorias")
def list_convocatorias():
    return db.list_convocatorias()


@app.get("/convocatorias/{convocatoria_id}")
def get_convocatoria(convocatoria_id: int):
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    return conv


@app.delete("/convocatorias/{convocatoria_id}", status_code=204)
def delete_convocatoria(convocatoria_id: int):
    deleted = db.delete_convocatoria(convocatoria_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")


# ---------------------------------------------------------------------------
# Subida de documentos
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/upload")
async def upload_documents(
    convocatoria_id: int,
    files: Annotated[list[UploadFile], File(description="Archivos a subir (PDF, DOCX, XLSX, TXT)")],
    etiquetas: Annotated[list[str], Form(description="Etiqueta por cada archivo en el mismo orden")],
):
    if db.get_convocatoria(convocatoria_id) is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    if len(files) != len(etiquetas):
        raise HTTPException(status_code=422, detail="El número de archivos y etiquetas debe coincidir.")

    valid_labels = set(extractors.LABEL_HEADERS.keys())
    documents, errors = [], []

    for file, etiqueta in zip(files, etiquetas):
        if etiqueta not in valid_labels:
            errors.append(f"'{file.filename}': etiqueta '{etiqueta}' no válida.")
            continue
        content = await file.read()
        try:
            texto = extractors.extract_text(content, file.filename)
        except ValueError as exc:
            errors.append(f"'{file.filename}': {exc}")
            continue
        documents.append({"etiqueta": etiqueta, "nombre_archivo": file.filename, "texto": texto})

    if errors and not documents:
        raise HTTPException(status_code=422, detail=errors)

    db.update_documentos(convocatoria_id, documents)
    context = extractors.build_context(documents)

    response: dict = {
        "convocatoria_id": convocatoria_id,
        "documentos_procesados": len(documents),
        "palabras_en_contexto": len(context.split()),
        "documentos": [{"nombre_archivo": d["nombre_archivo"], "etiqueta": d["etiqueta"]} for d in documents],
    }
    if errors:
        response["advertencias"] = errors
    return response


# ---------------------------------------------------------------------------
# Generación de entregables
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate")
def generate_outputs(convocatoria_id: int, body: GenerateRequest):
    """
    Genera uno o varios entregables para una convocatoria.

    La salida 4 usa generación multi-llamada (una llamada por sección de la memoria)
    para evitar cortes. Las demás salidas usan una sola llamada.
    Las salidas 4 y 5 generan también un JSON estructurado almacenado en SQLite.
    """
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    if not conv["documentos_json"]:
        raise HTTPException(
            status_code=422,
            detail="Esta convocatoria no tiene documentos. Sube los archivos antes de generar entregables.",
        )

    requested_types = {s.output_type for s in body.salidas}
    unknown = requested_types - set(range(1, 6))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}. Usa números del 1 al 5.",
        )

    context = extractors.build_context(conv["documentos_json"])
    client = _get_anthropic_client()
    generated: dict[str, str] = {}

    for salida_req in sorted(body.salidas, key=lambda s: s.output_type):
        output_type = salida_req.output_type
        instrucciones = salida_req.instrucciones_adicionales
        modo = salida_req.modo or "ABIERTA"

        try:
            if output_type == 4:
                md_text, json_sections = _generate_output_4(client, conv["nombre"], context, instrucciones)
                generated["4"] = md_text
                generated["4_json"] = json.dumps(json_sections, ensure_ascii=False)

            elif output_type == 5:
                user_prompt = _build_user_prompt(conv["nombre"], context, 5, instrucciones)
                md_text = _claude(client, system=p.SYSTEM_PROMPTS[5], user=user_prompt, max_tokens=p.MAX_TOKENS[5])
                generated["5"] = md_text
                generated["5_json"] = json.dumps(
                    _generate_output_5_json(client, md_text), ensure_ascii=False
                )

            else:
                user_prompt = _build_user_prompt(conv["nombre"], context, output_type, instrucciones, modo)
                generated[str(output_type)] = _claude(
                    client,
                    system=p.SYSTEM_PROMPTS[output_type],
                    user=user_prompt,
                    max_tokens=p.MAX_TOKENS[output_type],
                )

        except HTTPException:
            raise
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

    # Devolver texto + marcadores de JSON para que el frontend
    # pueda mostrar el botón .json sin necesidad de un campo adicional.
    result_entregables = {k: v for k, v in generated.items() if not k.endswith("_json")}
    for k in list(generated):
        if k.endswith("_json"):
            result_entregables[k] = True  # señal booleana; el texto completo no se manda al frontend

    return {
        "convocatoria_id": convocatoria_id,
        "generados": [k for k in generated if not k.endswith("_json")],
        "entregables": result_entregables,
    }


# ---------------------------------------------------------------------------
# Generación con streaming SSE (salida 4 emite progreso por sección)
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate/stream")
def generate_outputs_stream(convocatoria_id: int, body: GenerateRequest):
    """
    Genera entregables con respuesta SSE (Server-Sent Events).

    Eventos emitidos:
      {"tipo": "inicio_4", "total": N}              — salida 4: N secciones detectadas
      {"tipo": "progreso_4", "actual": i, "total": N} — salida 4: sección i completada
      {"tipo": "salida_completada", "num": N}        — cada salida completada
      {"tipo": "completado", "entregables": {...}}   — todo listo; incluye _json: true para señalar JSON disponible
      {"tipo": "error", "mensaje": "..."}            — error irrecuperable
    """
    # Validaciones síncronas antes de abrir el stream.
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    if not conv["documentos_json"]:
        raise HTTPException(
            status_code=422,
            detail="Esta convocatoria no tiene documentos. Sube los archivos antes de generar entregables.",
        )
    requested_types = {s.output_type for s in body.salidas}
    unknown = requested_types - set(range(1, 6))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}. Usa números del 1 al 5.",
        )

    context = extractors.build_context(conv["documentos_json"])
    client = _get_anthropic_client()

    def _evt(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def stream():
        generated: dict[str, str] = {}

        for salida_req in sorted(body.salidas, key=lambda s: s.output_type):
            output_type = salida_req.output_type
            instrucciones = salida_req.instrucciones_adicionales
            modo = salida_req.modo or "ABIERTA"

            try:
                if output_type == 4:
                    # Paso 1: extraer secciones (sin instrucciones: solo necesita los docs)
                    raw_sections = _claude(
                        client,
                        system=p.SECTION_EXTRACTOR_PROMPT,
                        user=f"Documentos de la convocatoria '{conv['nombre']}':\n\n{context}",
                        max_tokens=1500,
                    )
                    try:
                        secciones = _parse_json(raw_sections).get("secciones", [])
                    except Exception:
                        yield _evt({"tipo": "error", "mensaje": "No se pudieron identificar los apartados de la memoria. Comprueba que has subido la plantilla de memoria."})
                        return

                    n = len(secciones)
                    if n == 0:
                        yield _evt({"tipo": "error", "mensaje": "No se encontraron apartados en la plantilla de memoria."})
                        return

                    yield _evt({"tipo": "inicio_4", "total": n})

                    # Paso 2: generar markdown por sección
                    header = (
                        f"# Set de prompts para la memoria — {conv['nombre']}\n\n"
                        "> **Nota de uso:** El **Perfil Estratégico de Empresa** (documento de Ruta i40) "
                        "es la fuente principal de información sobre la empresa. Tenlo abierto antes de usar "
                        "estos prompts: cubre historia, actividad, datos económicos, estructura accionarial, "
                        "mercados y experiencia previa. Cada prompt indica únicamente la documentación "
                        "ADICIONAL específica del proyecto que el Perfil no cubre.\n\n---"
                    )
                    markdown_parts = [header]

                    for i, seccion in enumerate(secciones):
                        user_msg = (
                            f"Convocatoria: {conv['nombre']}\n"
                            f"Apartado: {seccion['codigo']} — {seccion['nombre']} "
                            f"(puntos_max: {seccion.get('puntos_max') or 'no especificado'}, "
                            f"habilitante: {seccion.get('es_habilitante', False)})\n\n"
                            f"Documentos de la convocatoria:\n{context}"
                        )
                        if instrucciones.strip():
                            user_msg += f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
                        raw_section = _claude(client, system=p.SECTION_PROMPT_SYSTEM, user=user_msg, max_tokens=2000)
                        markdown_parts.append(raw_section)

                        yield _evt({"tipo": "progreso_4", "actual": i + 1, "total": n})

                    markdown_4 = "\n\n---\n\n".join(markdown_parts)

                    # Paso 3: extraer JSON del markdown completo en una sola llamada.
                    raw_json_4 = _claude(
                        client,
                        system=p.OUTPUT_4_JSON_EXTRACTOR,
                        user=markdown_4,
                        max_tokens=8192,
                    )
                    try:
                        json_sections = _parse_json(raw_json_4)
                        if not isinstance(json_sections, list):
                            json_sections = []
                    except Exception:
                        json_sections = []

                    generated["4"] = markdown_4
                    generated["4_json"] = json.dumps(json_sections, ensure_ascii=False)

                elif output_type == 5:
                    user_prompt = _build_user_prompt(conv["nombre"], context, 5, instrucciones)
                    md_text = _claude(client, system=p.SYSTEM_PROMPTS[5], user=user_prompt, max_tokens=p.MAX_TOKENS[5])
                    generated["5"] = md_text
                    generated["5_json"] = json.dumps(
                        _generate_output_5_json(client, md_text), ensure_ascii=False
                    )

                else:
                    user_prompt = _build_user_prompt(conv["nombre"], context, output_type, instrucciones, modo)
                    generated[str(output_type)] = _claude(
                        client,
                        system=p.SYSTEM_PROMPTS[output_type],
                        user=user_prompt,
                        max_tokens=p.MAX_TOKENS[output_type],
                    )

                yield _evt({"tipo": "salida_completada", "num": output_type})

            except anthropic.APITimeoutError:
                yield _evt({"tipo": "error", "mensaje": f"La generación de la salida {output_type} superó el tiempo límite. Inténtalo de nuevo."})
                return
            except anthropic.APIError:
                yield _evt({"tipo": "error", "mensaje": f"Error al comunicarse con la API de Claude al generar la salida {output_type}. Inténtalo de nuevo."})
                return

        db.update_entregables(convocatoria_id, generated)

        # Devolver texto completo para renderizado + señal booleana para claves _json.
        result = {k: (True if k.endswith("_json") else v) for k, v in generated.items()}
        yield _evt({"tipo": "completado", "entregables": result})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Descarga de JSON estructurado (salidas 4 y 5)
# ---------------------------------------------------------------------------

@app.get("/convocatorias/{convocatoria_id}/json/{output_num}")
def get_output_json(convocatoria_id: int, output_num: int):
    """
    Devuelve el JSON estructurado de la salida 4 o 5 según el esquema del PRD v2.2 sección 12.
    El frontend lo descarga como fichero .json.
    """
    if output_num not in (4, 5):
        raise HTTPException(status_code=422, detail="Solo las salidas 4 y 5 tienen exportación JSON.")

    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    entregables = conv["entregables_json"]
    key = f"{output_num}_json"

    if key not in entregables:
        raise HTTPException(
            status_code=404,
            detail=f"La salida {output_num} aún no ha sido generada o no tiene JSON disponible.",
        )

    if output_num == 4:
        data = exporters.export_output_4(entregables[key])
    else:
        data = exporters.export_output_5(entregables[key])

    return data
