"""
ConvoKit backend — FastAPI application entry point.
"""

import json
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Annotated, Callable

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
import output6_template
import pricing
import prompts as p


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ConvocatoriaCreate(BaseModel):
    nombre: str


class SalidaRequest(BaseModel):
    output_type: int
    instrucciones_adicionales: str = ""
    modo: str | None = None  # Solo para salida 3: "ABIERTA" o "ANTICIPADA"


class GenerateRequest(BaseModel):
    salidas: list[SalidaRequest]


# ---------------------------------------------------------------------------
# Helpers de Claude
# ---------------------------------------------------------------------------

def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="La clave de la API de Claude no está configurada en el servidor.",
        )
    return anthropic.Anthropic(api_key=api_key)


def _claude(
    client: anthropic.Anthropic,
    system: str,
    user: str,
    max_tokens: int = 2000,
    model: str = pricing.MODELS["sonnet"],
    _track: Callable | None = None,
) -> str:
    """
    Wrapper de llamada síncrona a Claude.
    Si se pasa _track(model, input_tokens, output_tokens), registra el uso.
    """
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=180,
    )
    text = response.content[0].text
    if _track is not None:
        _track(model, response.usage.input_tokens, response.usage.output_tokens)
    return text


def _make_tracker(conv_id: int, salida: str) -> Callable:
    """Devuelve un callback que registra el uso de la API en la BD."""
    def track(model: str, input_tokens: int, output_tokens: int) -> None:
        cost = pricing.calculate_cost_eur(model, input_tokens, output_tokens)
        db.record_api_call(conv_id, salida, model, input_tokens, output_tokens, cost)
    return track


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    return text.strip()


def _parse_json(text: str) -> object:
    return json.loads(_strip_fences(text))


# ---------------------------------------------------------------------------
# Context slicing para salida 4 (reduce tokens por sección)
# ---------------------------------------------------------------------------

_SECTION_DOC_PRIORITY = [
    "plantilla_memoria", "convocatoria", "bases_reguladoras",
    "resolucion_anterior", "anexo", "documento_complementario",
]
_MAX_CHARS_PER_DOC = 22_000   # ~5 500 tokens por documento
_MAX_DOCS_PER_SECTION = 4


def _slice_context_for_section(documents_json: list) -> str:
    """
    Selecciona los documentos más relevantes para la generación de una sección.
    Reduce los tokens de entrada por llamada enviando solo los 4 documentos
    más prioritarios, truncados a 22 000 caracteres cada uno.
    """
    sorted_docs = sorted(
        documents_json,
        key=lambda d: _SECTION_DOC_PRIORITY.index(d.get("etiqueta", ""))
        if d.get("etiqueta") in _SECTION_DOC_PRIORITY else 99,
    )
    parts = []
    for doc in sorted_docs[:_MAX_DOCS_PER_SECTION]:
        label = extractors.LABEL_HEADERS.get(doc.get("etiqueta", ""), "DOCUMENTO")
        text = doc.get("texto", "")
        if len(text) > _MAX_CHARS_PER_DOC:
            text = text[:_MAX_CHARS_PER_DOC] + "\n[... truncado ...]"
        parts.append(f"=== {label} ===\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Generación de salida 1 (dos llamadas consecutivas)
# ---------------------------------------------------------------------------

def _generate_output_1(
    client: anthropic.Anthropic,
    conv_name: str,
    context: str,
    instrucciones: str = "",
    model: str | None = None,
    _track: Callable | None = None,
) -> str:
    """
    La guía del consultor se genera en dos llamadas sucesivas para evitar cortes.

    Llamada 1: genera la guía desde el principio con el límite de 8192 tokens.
    Llamada 2: recibe la primera parte + los documentos y continúa desde el corte,
               completando las secciones pendientes (Plan de trabajo, Alertas...).
    Resultado: concatenación de ambas partes como un único documento markdown.
    """
    model = model or pricing.MODEL_PER_OUTPUT[1]

    user_1 = _build_user_prompt(conv_name, context, 1, instrucciones)
    part_1 = _claude(
        client,
        system=p.SYSTEM_PROMPTS[1],
        user=user_1,
        max_tokens=p.MAX_TOKENS[1],
        model=model,
        _track=_track,
    )

    instr_block = (
        f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
        if instrucciones.strip() else ""
    )
    user_2 = (
        f"Documentos de la convocatoria '{conv_name}':\n\n{context}\n\n"
        f"---\n\n"
        f"Has generado la primera parte de la guía interna. Aquí está el texto ya producido:\n\n"
        f"{part_1}\n\n"
        f"---\n\n"
        f"Continúa EXACTAMENTE donde se ha cortado el texto anterior. "
        f"Completa las secciones que estén incompletas o no hayan aparecido aún "
        f"(incluyendo ## Plan de trabajo y ## Alertas de cumplimiento si faltan o quedaron sin terminar). "
        f"No repitas ninguna sección ya completada en la primera parte. "
        f"Empieza directamente con el contenido que falta, sin preámbulo."
        f"{instr_block}"
    )
    part_2 = _claude(
        client,
        system=p.SYSTEM_PROMPTS[1],
        user=user_2,
        max_tokens=p.MAX_TOKENS[1],
        model=model,
        _track=_track,
    )

    return part_1.rstrip() + "\n\n" + part_2.lstrip()


# ---------------------------------------------------------------------------
# Generación de salida 6 (evaluador HTML interactivo)
# ---------------------------------------------------------------------------

def _generate_output_6(
    client: anthropic.Anthropic,
    conv_name: str,
    context: str,
    instrucciones: str = "",
    model: str | None = None,
    _track: Callable | None = None,
) -> str:
    """
    Generación de la salida 6 (evaluador HTML interactivo).
    Paso 1: Claude extrae JSON de config de los documentos.
    Paso 2: Python construye el HTML desde la plantilla estática.
    """
    model = model or pricing.MODEL_PER_OUTPUT.get(6, pricing.MODELS["haiku"])

    instr_block = (
        f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
        if instrucciones.strip() else ""
    )
    user_msg = (
        f"Documentos de la convocatoria '{conv_name}':\n\n{context}"
        + instr_block
        + "\n\nGenera el objeto JSON de configuración del evaluador siguiendo exactamente el esquema del system prompt."
    )

    raw_config = _claude(
        client,
        system=p.OUTPUT_6_CONFIG_PROMPT,
        user=user_msg,
        max_tokens=p.MAX_TOKENS[6],
        model=model,
        _track=_track,
    )

    try:
        config = _parse_json(raw_config)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudo generar la configuración del evaluador. Comprueba que los documentos contienen los criterios de la convocatoria.",
        )

    return output6_template.build_output_6_html(config)


# ---------------------------------------------------------------------------
# Generación de salida 4
# ---------------------------------------------------------------------------

def _generate_output_4(
    client: anthropic.Anthropic,
    conv_name: str,
    documents_json: list,
    instrucciones: str = "",
    model: str | None = None,
    _track: Callable | None = None,
    _progress_cb: Callable | None = None,
) -> tuple[str, list[dict]]:
    """
    Generación multi-llamada de la salida 4.

    Flujo:
    1. Extraer lista de secciones (contexto completo, un solo documento relevante basta).
    2. Generar cada sección con contexto reducido (slicing por prioridad de documento).
       Pausa de 2 s entre secciones para reducir carga en la API.
    3. Extracción JSON del markdown completo con una sola llamada adicional.
    """
    model = model or pricing.MODEL_PER_OUTPUT[4]
    full_context = extractors.build_context(documents_json)

    # Paso 1: extraer secciones
    raw_sections = _claude(
        client,
        system=p.SECTION_EXTRACTOR_PROMPT,
        user=f"Documentos de la convocatoria '{conv_name}':\n\n{full_context}",
        max_tokens=1500,
        model=model,
        _track=_track,
    )
    try:
        secciones = _parse_json(raw_sections).get("secciones", [])
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudieron identificar los apartados de la memoria. "
                   "Comprueba que has subido la plantilla de memoria.",
        )

    if not secciones:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron apartados en la plantilla de memoria.",
        )

    # Paso 2: generar markdown por sección con contexto reducido
    header = (
        f"# Set de prompts para la memoria — {conv_name}\n\n"
        "> **Nota de uso:** El **Perfil Estratégico de Empresa** (documento de Ruta i40) "
        "es la fuente principal de información sobre la empresa. Tenlo abierto antes de usar "
        "estos prompts: cubre historia, actividad, datos económicos, estructura accionarial, "
        "mercados y experiencia previa. Cada prompt indica únicamente la documentación "
        "ADICIONAL específica del proyecto que el Perfil no cubre.\n\n---"
    )
    markdown_parts = [header]
    section_context = _slice_context_for_section(documents_json)

    for i, seccion in enumerate(secciones):
        if i > 0:
            time.sleep(2)  # Pausa entre secciones para reducir carga en la API

        user_msg = (
            f"Convocatoria: {conv_name}\n"
            f"Apartado: {seccion['codigo']} — {seccion['nombre']} "
            f"(puntos_max: {seccion.get('puntos_max') or 'no especificado'}, "
            f"habilitante: {seccion.get('es_habilitante', False)})\n\n"
            f"Documentos de la convocatoria:\n{section_context}"
        )
        if instrucciones.strip():
            user_msg += f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"

        raw_section = _claude(
            client,
            system=p.SECTION_PROMPT_SYSTEM,
            user=user_msg,
            max_tokens=4096,
            model=model,
            _track=_track,
        )
        markdown_parts.append(raw_section)

        if _progress_cb:
            _progress_cb(i + 1, len(secciones))

    markdown = "\n\n---\n\n".join(markdown_parts)

    # Paso 3: extracción JSON del markdown completo en una sola llamada (siempre Haiku)
    time.sleep(2)
    raw_json = _claude(
        client,
        system=p.OUTPUT_4_JSON_EXTRACTOR,
        user=markdown,
        max_tokens=8192,
        model=pricing.MODELS["haiku"],
        _track=_track,
    )
    try:
        json_sections = _parse_json(raw_json)
        if not isinstance(json_sections, list):
            json_sections = []
    except Exception:
        json_sections = []

    return markdown, json_sections


# ---------------------------------------------------------------------------
# Generación de JSON de salida 5
# ---------------------------------------------------------------------------

def _generate_output_5_json(
    client: anthropic.Anthropic,
    md_text: str,
    model: str | None = None,
    _track: Callable | None = None,
) -> list[dict]:
    model = model or pricing.MODEL_PER_OUTPUT[5]
    raw = _claude(
        client,
        system=p.OUTPUT_5_JSON_CONVERTER,
        user=f"Convierte la siguiente lista de documentación a JSON:\n\n{md_text}",
        max_tokens=3000,
        model=model,
        _track=_track,
    )
    try:
        return _parse_json(raw)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

def _build_user_prompt(
    conv_name: str,
    context: str,
    output_type: int,
    instrucciones: str = "",
    modo: str = "ABIERTA",
) -> str:
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


# ---------------------------------------------------------------------------
# Procesador de jobs en segundo plano
# ---------------------------------------------------------------------------

def _process_job(job_id: int, conv_id: int, salida_requests: list[dict]) -> None:
    """
    Background thread. Procesa cada salida secuencialmente, actualiza el progreso
    en SQLite y persiste resultados parciales. No requiere que el navegador esté abierto.
    """
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        conv = db.get_convocatoria(conv_id)
        if not conv:
            db.update_job(job_id, "error", {"error": "Convocatoria no encontrada."})
            return

        conv_name = conv["nombre"]
        documents_json = conv["documentos_json"]
        context = extractors.build_context(documents_json)

        progress = {"outputs": {str(s["output_type"]): {"status": "queued"} for s in salida_requests}}
        db.update_job(job_id, "running", progress)

        for salida_req in sorted(salida_requests, key=lambda s: s["output_type"]):
            output_type = salida_req["output_type"]
            instrucciones = salida_req.get("instrucciones_adicionales", "")
            modo = salida_req.get("modo") or "ABIERTA"
            key = str(output_type)

            progress["outputs"][key] = {"status": "running"}
            db.update_job(job_id, "running", progress)

            salida_costs: list[float] = []
            model = pricing.MODEL_PER_OUTPUT.get(output_type, pricing.MODELS["sonnet"])

            def track(mdl: str, in_tok: int, out_tok: int) -> None:
                cost = pricing.calculate_cost_eur(mdl, in_tok, out_tok)
                db.record_api_call(conv_id, key, mdl, in_tok, out_tok, cost)
                salida_costs.append(cost)

            generated: dict[str, str] = {}

            try:
                if output_type == 1:
                    generated["1"] = _generate_output_1(
                        client, conv_name, context, instrucciones,
                        model=model, _track=track,
                    )

                elif output_type == 4:
                    def progress_cb(actual: int, total: int) -> None:
                        progress["output4_progress"] = {"actual": actual, "total": total}
                        db.update_job(job_id, "running", progress)

                    md_text, json_secs = _generate_output_4(
                        client, conv_name, documents_json, instrucciones,
                        model=model, _track=track, _progress_cb=progress_cb,
                    )
                    generated["4"] = md_text
                    generated["4_json"] = json.dumps(json_secs, ensure_ascii=False)

                elif output_type == 5:
                    user_prompt = _build_user_prompt(conv_name, context, 5, instrucciones)
                    md_text = _claude(
                        client, system=p.SYSTEM_PROMPTS[5], user=user_prompt,
                        max_tokens=p.MAX_TOKENS[5], model=model, _track=track,
                    )
                    generated["5"] = md_text
                    generated["5_json"] = json.dumps(
                        _generate_output_5_json(client, md_text, model=model, _track=track),
                        ensure_ascii=False,
                    )

                elif output_type == 6:
                    generated["6"] = _generate_output_6(
                        client, conv_name, context, instrucciones,
                        model=model, _track=track,
                    )

                else:
                    user_prompt = _build_user_prompt(conv_name, context, output_type, instrucciones, modo)
                    generated[key] = _claude(
                        client, system=p.SYSTEM_PROMPTS[output_type], user=user_prompt,
                        max_tokens=p.MAX_TOKENS[output_type], model=model, _track=track,
                    )

                db.update_entregables(conv_id, generated)

                total_cost = sum(salida_costs)
                progress["outputs"][key] = {"status": "completed", "cost_eur": round(total_cost, 6)}
                progress.pop("output4_progress", None)

            except Exception as exc:
                progress["outputs"][key] = {"status": "error", "error": str(exc)}

            db.update_job(job_id, "running", progress)

        has_errors = any(
            v.get("status") == "error" for v in progress["outputs"].values()
        )
        db.update_job(job_id, "error" if has_errors else "completed", progress)

    except Exception as exc:
        try:
            db.update_job(job_id, "error", {"error": str(exc)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.reset_stuck_jobs()
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
# Convocatorias — CRUD
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
    if not db.delete_convocatoria(convocatoria_id):
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
# Generación asíncrona con cola (endpoint principal)
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate/async", status_code=202)
def generate_async(convocatoria_id: int, body: GenerateRequest):
    """
    Inicia la generación en un thread de fondo y devuelve el job_id inmediatamente.
    El navegador puede cerrarse; los resultados se persisten en SQLite conforme se completan.
    Consultar /jobs/{job_id} para seguir el progreso.
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
    unknown = requested_types - set(range(1, 7))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}. Usa números del 1 al 6.",
        )

    salidas_list = [s.model_dump() for s in body.salidas]
    job_id = db.create_job(convocatoria_id, salidas_list)

    thread = threading.Thread(
        target=_process_job,
        args=(job_id, convocatoria_id, salidas_list),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return job


# ---------------------------------------------------------------------------
# Generación síncrona (sin streaming — compatibilidad)
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate")
def generate_outputs(convocatoria_id: int, body: GenerateRequest):
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    if not conv["documentos_json"]:
        raise HTTPException(
            status_code=422,
            detail="Esta convocatoria no tiene documentos. Sube los archivos antes de generar entregables.",
        )
    requested_types = {s.output_type for s in body.salidas}
    unknown = requested_types - set(range(1, 7))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}.",
        )

    context = extractors.build_context(conv["documentos_json"])
    client = _get_anthropic_client()
    generated: dict[str, str] = {}

    for salida_req in sorted(body.salidas, key=lambda s: s.output_type):
        output_type = salida_req.output_type
        instrucciones = salida_req.instrucciones_adicionales
        modo = salida_req.modo or "ABIERTA"
        model = pricing.MODEL_PER_OUTPUT.get(output_type, pricing.MODELS["sonnet"])
        track = _make_tracker(convocatoria_id, str(output_type))

        try:
            if output_type == 1:
                generated["1"] = _generate_output_1(
                    client, conv["nombre"], context, instrucciones,
                    model=model, _track=track,
                )

            elif output_type == 4:
                md_text, json_sections = _generate_output_4(
                    client, conv["nombre"], conv["documentos_json"], instrucciones,
                    model=model, _track=track,
                )
                generated["4"] = md_text
                generated["4_json"] = json.dumps(json_sections, ensure_ascii=False)

            elif output_type == 5:
                user_prompt = _build_user_prompt(conv["nombre"], context, 5, instrucciones)
                md_text = _claude(
                    client, system=p.SYSTEM_PROMPTS[5], user=user_prompt,
                    max_tokens=p.MAX_TOKENS[5], model=model, _track=track,
                )
                generated["5"] = md_text
                generated["5_json"] = json.dumps(
                    _generate_output_5_json(client, md_text, model=model, _track=track),
                    ensure_ascii=False,
                )

            elif output_type == 6:
                generated["6"] = _generate_output_6(
                    client, conv["nombre"], context, instrucciones,
                    model=model, _track=track,
                )

            else:
                user_prompt = _build_user_prompt(conv["nombre"], context, output_type, instrucciones, modo)
                generated[str(output_type)] = _claude(
                    client, system=p.SYSTEM_PROMPTS[output_type], user=user_prompt,
                    max_tokens=p.MAX_TOKENS[output_type], model=model, _track=track,
                )

        except HTTPException:
            raise
        except anthropic.APITimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"La generación de la salida {output_type} superó el tiempo límite.",
            )
        except anthropic.APIError:
            raise HTTPException(
                status_code=502,
                detail=f"Error al comunicarse con la API de Claude al generar la salida {output_type}.",
            )

    db.update_entregables(convocatoria_id, generated)
    result_entregables = {k: (True if k.endswith("_json") else v) for k, v in generated.items()}
    return {
        "convocatoria_id": convocatoria_id,
        "generados": [k for k in generated if not k.endswith("_json")],
        "entregables": result_entregables,
    }


# ---------------------------------------------------------------------------
# Generación con streaming SSE (compatibilidad — usa los modelos correctos)
# ---------------------------------------------------------------------------

@app.post("/convocatorias/{convocatoria_id}/generate/stream")
def generate_outputs_stream(convocatoria_id: int, body: GenerateRequest):
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    if not conv["documentos_json"]:
        raise HTTPException(
            status_code=422,
            detail="Esta convocatoria no tiene documentos. Sube los archivos antes de generar entregables.",
        )
    requested_types = {s.output_type for s in body.salidas}
    unknown = requested_types - set(range(1, 7))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Tipos de salida no válidos: {sorted(unknown)}.",
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
            model = pricing.MODEL_PER_OUTPUT.get(output_type, pricing.MODELS["sonnet"])
            track = _make_tracker(convocatoria_id, str(output_type))

            try:
                if output_type == 1:
                    generated["1"] = _generate_output_1(
                        client, conv["nombre"], context, instrucciones,
                        model=model, _track=track,
                    )

                elif output_type == 4:
                    # Paso 1: extraer secciones
                    raw_sections = _claude(
                        client,
                        system=p.SECTION_EXTRACTOR_PROMPT,
                        user=f"Documentos de la convocatoria '{conv['nombre']}':\n\n{context}",
                        max_tokens=1500,
                        model=model,
                        _track=track,
                    )
                    try:
                        secciones = _parse_json(raw_sections).get("secciones", [])
                    except Exception:
                        yield _evt({"tipo": "error", "mensaje": "No se pudieron identificar los apartados de la memoria."})
                        return

                    n = len(secciones)
                    if n == 0:
                        yield _evt({"tipo": "error", "mensaje": "No se encontraron apartados en la plantilla de memoria."})
                        return

                    yield _evt({"tipo": "inicio_4", "total": n})

                    header = (
                        f"# Set de prompts para la memoria — {conv['nombre']}\n\n"
                        "> **Nota de uso:** El **Perfil Estratégico de Empresa** (documento de Ruta i40) "
                        "es la fuente principal de información sobre la empresa. Tenlo abierto antes de usar "
                        "estos prompts: cubre historia, actividad, datos económicos, estructura accionarial, "
                        "mercados y experiencia previa. Cada prompt indica únicamente la documentación "
                        "ADICIONAL específica del proyecto que el Perfil no cubre.\n\n---"
                    )
                    markdown_parts = [header]
                    section_context = _slice_context_for_section(conv["documentos_json"])

                    for i, seccion in enumerate(secciones):
                        if i > 0:
                            time.sleep(2)
                        user_msg = (
                            f"Convocatoria: {conv['nombre']}\n"
                            f"Apartado: {seccion['codigo']} — {seccion['nombre']} "
                            f"(puntos_max: {seccion.get('puntos_max') or 'no especificado'}, "
                            f"habilitante: {seccion.get('es_habilitante', False)})\n\n"
                            f"Documentos de la convocatoria:\n{section_context}"
                        )
                        if instrucciones.strip():
                            user_msg += f"\n\nINSTRUCCIONES ADICIONALES DEL CONSULTOR: {instrucciones.strip()}"
                        raw_section = _claude(
                            client, system=p.SECTION_PROMPT_SYSTEM, user=user_msg,
                            max_tokens=4096, model=model, _track=track,
                        )
                        markdown_parts.append(raw_section)
                        yield _evt({"tipo": "progreso_4", "actual": i + 1, "total": n})

                    markdown_4 = "\n\n---\n\n".join(markdown_parts)
                    time.sleep(2)
                    raw_json_4 = _claude(
                        client, system=p.OUTPUT_4_JSON_EXTRACTOR, user=markdown_4,
                        max_tokens=8192, model=pricing.MODELS["haiku"], _track=track,
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
                    md_text = _claude(
                        client, system=p.SYSTEM_PROMPTS[5], user=user_prompt,
                        max_tokens=p.MAX_TOKENS[5], model=model, _track=track,
                    )
                    generated["5"] = md_text
                    generated["5_json"] = json.dumps(
                        _generate_output_5_json(client, md_text, model=model, _track=track),
                        ensure_ascii=False,
                    )

                elif output_type == 6:
                    generated["6"] = _generate_output_6(
                        client, conv["nombre"], context, instrucciones,
                        model=model, _track=track,
                    )

                else:
                    user_prompt = _build_user_prompt(conv["nombre"], context, output_type, instrucciones, modo)
                    generated[str(output_type)] = _claude(
                        client, system=p.SYSTEM_PROMPTS[output_type], user=user_prompt,
                        max_tokens=p.MAX_TOKENS[output_type], model=model, _track=track,
                    )

                yield _evt({"tipo": "salida_completada", "num": output_type})

            except anthropic.APITimeoutError:
                yield _evt({"tipo": "error", "mensaje": f"La salida {output_type} superó el tiempo límite."})
                return
            except anthropic.APIError:
                yield _evt({"tipo": "error", "mensaje": f"Error de API al generar la salida {output_type}."})
                return

        db.update_entregables(convocatoria_id, generated)
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
        return exporters.export_output_4(entregables[key])
    else:
        return exporters.export_output_5(entregables[key])


# ---------------------------------------------------------------------------
# Estadísticas globales de uso de la API
# ---------------------------------------------------------------------------

@app.get("/stats")
def get_stats():
    return db.get_api_stats()
