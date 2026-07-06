"""
ConvoKit backend — FastAPI application entry point.
"""

import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Callable

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

import resend
import database as db
import exporters
import extractors
import output3_template
import output6_template
import pricing
import prompts as p
import result_email


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ConvocatoriaCreate(BaseModel):
    nombre: str


class SalidaRequest(BaseModel):
    output_type: int
    instrucciones_adicionales: str = ""
    modo: str | None = None  # Solo para salida 3: "ABIERTA" o "ANTICIPADA"
    variante: str | None = None  # Solo para salida 3: "A", "B" o "C" (distribución de fondos)
    incluir_evaluador: bool = False  # Solo para salida 3: embebe el evaluador de encaje


class GenerateRequest(BaseModel):
    salidas: list[SalidaRequest]


class LandingSeoRequest(BaseModel):
    seo_title: str
    meta_description: str
    slug: str


class LandingVariantRequest(BaseModel):
    variante: str  # "A", "B" o "C"


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


def _get_existing_cfg(entregables: dict) -> dict | None:
    """
    Recupera el CFG del evaluador ya generado para esta convocatoria (clave
    "6_cfg" en entregables_json), si existe, para que la salida 3 (embebido) y
    la salida 6 (standalone) lo compartan en vez de generarlo cada una por su
    lado y arriesgar que las preguntas diverjan.
    """
    raw = entregables.get("6_cfg")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _instr_block(instrucciones: str) -> str:
    """
    Devuelve el bloque de instrucción del usuario, con rango de prioridad explícita.
    Debe colocarse SIEMPRE al final del prompt (máxima recencia): si va antes del
    volcado de documentos, el contexto lo entierra y el modelo lo ignora.
    """
    text = (instrucciones or "").strip()
    if not text:
        return ""
    return (
        "\n\n=== INSTRUCCIÓN PRIORITARIA DEL USUARIO ===\n"
        f"{text}\n"
        "\n"
        "ESTA INSTRUCCIÓN ES OBLIGATORIA. Tiene PRIORIDAD ABSOLUTA sobre el system prompt "
        "y sobre los datos de los documentos. Aplícala de forma literal. En particular:\n"
        "- Si indica un año concreto (ej. '2027'), ese año debe aparecer en el H2 de la "
        "sección de importe y donde corresponda, INDEPENDIENTEMENTE del año que figuren en "
        "los documentos. NO uses el año de los documentos cuando el usuario ha especificado otro.\n"
        "- Si indica texto de asterisco o nota al pie (ej. '*Basada en datos de 2025. Pdte "
        "convocatoria.'), inclúyelo EXACTAMENTE como lo escribe el usuario.\n"
        "- Si dice que NO menciones algo (ej. 'no menciones el periodo de ejecución'), "
        "NO lo menciones bajo ningún concepto.\n"
        "=== FIN INSTRUCCIÓN PRIORITARIA ==="
    )


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

    instr_block = _instr_block(instrucciones)
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
# Generación de salida 3 (landing page HTML desplegable)
# ---------------------------------------------------------------------------

def _generate_evaluador_cfg(
    client: anthropic.Anthropic,
    conv_name: str,
    context: str,
    instrucciones: str = "",
    model: str | None = None,
    _track: Callable | None = None,
) -> dict:
    """
    Genera el objeto JSON de configuración del evaluador (CFG): elegibilidad,
    baremo, datos_proyecto, textos. Lo comparten la salida 6 (evaluador
    standalone) y la salida 3 cuando embebe el evaluador, para que ambos
    hagan exactamente las mismas preguntas.
    """
    model = model or pricing.MODEL_PER_OUTPUT.get(6, pricing.MODELS["sonnet"])

    user_msg = (
        f"Documentos de la convocatoria '{conv_name}':\n\n{context}"
        + "\n\nExtrae el objeto JSON de configuración del evaluador siguiendo las instrucciones del system prompt."
        + _instr_block(instrucciones)
    )

    raw = _claude(
        client,
        system=p.OUTPUT_6_CONFIG_PROMPT,
        user=user_msg,
        max_tokens=p.MAX_TOKENS[6],
        model=model,
        _track=_track,
    )
    # Try strict parse first, then fall back to extracting the outermost { ... }
    config = None
    parse_err = ""
    try:
        config = _parse_json(raw)
    except Exception as e1:
        parse_err = str(e1)
        match = re.search(r'\{.*\}', raw.strip(), re.DOTALL)
        if match:
            try:
                config = json.loads(match.group(0))
            except Exception as e2:
                parse_err = str(e2)

    if config is None:
        tail = repr(raw[-150:]) if raw else "(vacío)"
        raise HTTPException(
            status_code=502,
            detail=f"JSON inválido: {parse_err[:120]} | fin_respuesta: {tail}",
        )
    return config


def _generate_output_3(
    client: anthropic.Anthropic,
    conv_name: str,
    context: str,
    instrucciones: str = "",
    modo: str = "ABIERTA",
    variant: str = "A",
    incluir_evaluador: bool = False,
    existing_cfg: dict | None = None,
    model: str | None = None,
    _track: Callable | None = None,
) -> tuple[str, dict, dict | None]:
    """
    Generación de la salida 3 (landing page para WordPress).
    Claude devuelve los campos SEO + el cuerpo HTML (bloques scoped, sin fondos,
    con el marcador del evaluador embebido si INCLUIR_EVALUADOR: SI). El backend
    separa ambas partes, aplica la variante de distribución, y envuelve el cuerpo
    en la plantilla estática scoped bajo #innovate-ayuda-landing-{slug}.

    Si incluir_evaluador es True, genera (o reutiliza existing_cfg) el mismo CFG
    que usa la salida 6, para que ambas compartan las mismas preguntas en vez de
    generarlas por separado y arriesgar que diverjan.

    Devuelve (html_completo, seo, cfg_usado). cfg_usado es None si no se pidió
    evaluador embebido. Si no es None y existing_cfg era None, el llamador debe
    persistirlo como "6_cfg" para que una futura salida 6 (o una regeneración de
    esta misma landing) lo reutilice sin gastar otra llamada a Claude.
    """
    model = model or pricing.MODEL_PER_OUTPUT.get(3, pricing.MODELS["haiku"])
    variant = output3_template.normalize_variant(variant)

    cfg_usado = None
    if incluir_evaluador:
        cfg_usado = existing_cfg or _generate_evaluador_cfg(
            client, conv_name, context, instrucciones, _track=_track,
        )

    user_prompt = _build_user_prompt(conv_name, context, 3, instrucciones, modo, incluir_evaluador)
    raw = _claude(
        client,
        system=p.SYSTEM_PROMPTS[3],
        user=user_prompt,
        max_tokens=p.MAX_TOKENS[3],
        model=model,
        _track=_track,
    )
    seo, body = output3_template.parse_landing_response(raw, fallback_name=conv_name)
    html = output3_template.build_output_3_html(body, seo["slug"], variant, cfg=cfg_usado)
    seo_full = {
        **seo, "body_html": body, "variant": variant, "confirmed": False,
        "incluir_evaluador": incluir_evaluador,
    }
    return html, seo_full, cfg_usado


# ---------------------------------------------------------------------------
# Generación de salida 6 (evaluador HTML interactivo)
# ---------------------------------------------------------------------------

def _generate_output_6(
    client: anthropic.Anthropic,
    conv_name: str,
    context: str,
    instrucciones: str = "",
    existing_cfg: dict | None = None,
    model: str | None = None,
    _track: Callable | None = None,
) -> tuple[str, dict]:
    """
    Generación de la salida 6 (evaluador HTML interactivo standalone).
    Reutiliza existing_cfg (por ejemplo si la salida 3 ya generó el CFG al
    embeber el evaluador) en vez de llamar a Claude de nuevo, si se aporta.
    Devuelve (html, cfg) para que el llamador pueda persistir el CFG usado.
    """
    config = existing_cfg or _generate_evaluador_cfg(
        client, conv_name, context, instrucciones, model=model, _track=_track,
    )
    return output6_template.build_output_6_html(config), config


# ---------------------------------------------------------------------------
# Generación de salida 4
# ---------------------------------------------------------------------------

def _dedupe_apartado_codigos(apartados: list[dict]) -> None:
    """Desambigua códigos de apartado repetidos añadiendo un sufijo numérico, in place."""
    seen: dict[str, int] = {}
    for apartado in apartados:
        codigo = apartado.get("codigo") or ""
        count = seen.get(codigo, 0)
        seen[codigo] = count + 1
        if count > 0:
            apartado["codigo"] = f"{codigo}-{count + 1}"


def _consolidate_campos_empresa(
    client: anthropic.Anthropic,
    apartados: list[dict],
    _track: Callable | None = None,
) -> list[dict]:
    """
    Recoge las propuestas de dato_empresa de todos los apartados ya generados,
    las deduplica semánticamente con una llamada a Claude y remapea in place
    el ref_campo_empresa de cada apartado al id final del catálogo.
    """
    propuestas = []
    for apartado in apartados:
        for inp in apartado.get("inputs", []):
            if inp.get("tipo") == "dato_empresa" and inp.get("ref_campo_empresa"):
                propuestas.append({
                    "codigo_apartado": apartado.get("codigo", ""),
                    "id_propuesto": inp["ref_campo_empresa"],
                    "label": inp.get("label", ""),
                    "ayuda": inp.get("ayuda", ""),
                })

    if not propuestas:
        return []

    try:
        raw = _claude(
            client,
            system=p.OUTPUT_4_CAMPOS_EMPRESA_CONSOLIDATOR,
            user=json.dumps(propuestas, ensure_ascii=False),
            max_tokens=3000,
            model=pricing.MODELS["haiku"],
            _track=_track,
        )
        data = _parse_json(raw)
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    campos_empresa = data.get("campos_empresa") or []
    remapeo = data.get("remapeo") or []
    remap_index = {
        (r.get("codigo_apartado"), r.get("id_propuesto")): r.get("id_final")
        for r in remapeo if isinstance(r, dict)
    }

    for apartado in apartados:
        codigo = apartado.get("codigo", "")
        for inp in apartado.get("inputs", []):
            if inp.get("tipo") == "dato_empresa" and inp.get("ref_campo_empresa"):
                id_final = remap_index.get((codigo, inp["ref_campo_empresa"]))
                if id_final:
                    inp["ref_campo_empresa"] = id_final

    return campos_empresa if isinstance(campos_empresa, list) else []


def _extract_datos_aplicativo(
    client: anthropic.Anthropic,
    full_context: str,
    campos_empresa: list[dict],
    _track: Callable | None = None,
) -> list[dict]:
    """Extrae los datos de aplicativo/formulario (no narrativos) del contexto completo."""
    campos_conocidos = [{"id": c.get("id"), "nombre": c.get("nombre")} for c in campos_empresa]
    user_msg = (
        f"Documentos de la convocatoria:\n\n{full_context}\n\n"
        "Datos de empresa ya cubiertos como contenido de memoria (no los dupliques aquí):\n"
        f"{json.dumps(campos_conocidos, ensure_ascii=False)}"
    )
    try:
        raw = _claude(
            client,
            system=p.OUTPUT_4_DATOS_APLICATIVO_EXTRACTOR,
            user=user_msg,
            max_tokens=4096,
            model=pricing.MODELS["haiku"],
            _track=_track,
        )
        data = _parse_json(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _generate_output_4(
    client: anthropic.Anthropic,
    conv_name: str,
    documents_json: list,
    instrucciones: str = "",
    model: str | None = None,
    _track: Callable | None = None,
    _progress_cb: Callable | None = None,
) -> tuple[str, dict]:
    """
    Generación multi-llamada de la salida 4. Produce el objeto raíz del
    contrato de exportación v2.0 (docs/contrato-convokit.md): version_esquema,
    convocatoria, campos_empresa, apartados, datos_aplicativo.

    Flujo:
    1. Extraer metadatos de la convocatoria y lista de secciones.
    2. Generar cada sección con contexto reducido: markdown + JSON tipado
       (inputs con tipo/nivel, flags de rentabilidad/inversión).
       Pausa entre secciones para reducir carga en la API.
    3. Desambiguar códigos de apartado repetidos.
    4. Consolidar el catálogo de campos_empresa (dedup semántico entre apartados).
    5. Extraer los datos_aplicativo del contexto completo (bases/formulario).
    """
    model = model or pricing.MODEL_PER_OUTPUT[4]
    full_context = extractors.build_context(documents_json)

    # Paso 1: metadatos de convocatoria + secciones
    raw_sections = _claude(
        client,
        system=p.SECTION_EXTRACTOR_PROMPT,
        user=f"Documentos de la convocatoria '{conv_name}':\n\n{full_context}",
        max_tokens=2000,
        model=model,
        _track=_track,
    )
    try:
        parsed_step1 = _parse_json(raw_sections)
        secciones = parsed_step1.get("secciones", [])
        conv_meta = parsed_step1.get("convocatoria") or {}
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

    # Paso 2: generar markdown + JSON tipado por sección con contexto reducido
    header = (
        f"# Set de prompts para la memoria — {conv_name}\n\n"
        "> **Nota de uso:** El **Perfil Estratégico de Empresa** (documento de Ruta i40) "
        "es la fuente principal de información sobre la empresa. Tenlo abierto antes de usar "
        "estos prompts: cubre historia, actividad, datos económicos, estructura accionarial, "
        "mercados y experiencia previa. Cada prompt indica únicamente la documentación "
        "ADICIONAL específica del proyecto que el Perfil no cubre.\n\n---"
    )
    markdown_parts = [header]
    apartados: list[dict] = []
    section_context = _slice_context_for_section(documents_json)

    for i, seccion in enumerate(secciones):
        if i > 0:
            time.sleep(5)  # Pausa entre secciones para evitar rate limits

        user_msg = (
            f"Convocatoria: {conv_name}\n"
            f"Apartado: {seccion['codigo']} — {seccion['nombre']} "
            f"(puntos_max: {seccion.get('puntos_max') or 'no especificado'}, "
            f"habilitante: {seccion.get('es_habilitante', False)})\n\n"
            f"Documentos de la convocatoria:\n{section_context}"
        )
        user_msg += _instr_block(instrucciones)

        # Retry con backoff para tolerar rate limits transitorios
        raw_section = None
        for attempt in range(3):
            try:
                raw_section = _claude(
                    client,
                    system=p.SECTION_PROMPT_SYSTEM,
                    user=user_msg,
                    max_tokens=8192,
                    model=model,
                    _track=_track,
                )
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(15 * (attempt + 1))
                else:
                    raw_section = f"<!-- Error generando sección {seccion['codigo']}: {exc} -->"
        markdown_parts.append(raw_section or "")

        # Extraer JSON tipado de esta sección individualmente (evita truncar con el markdown completo)
        try:
            raw_json_sec = _claude(
                client,
                system=p.OUTPUT_4_JSON_EXTRACTOR,
                user=raw_section,
                max_tokens=4096,
                model=pricing.MODELS["haiku"],
                _track=_track,
            )
            parsed_sec = _parse_json(raw_json_sec)
            if isinstance(parsed_sec, dict):
                apartados.append(parsed_sec)
        except Exception:
            pass  # sección sin JSON válido: se omite, el markdown queda intacto

        if _progress_cb:
            _progress_cb(i + 1, len(secciones))

    markdown = "\n\n---\n\n".join(markdown_parts)

    # Paso 3: desambiguar códigos repetidos
    _dedupe_apartado_codigos(apartados)

    # Paso 4: consolidar catálogo de campos_empresa y remapear referencias
    campos_empresa = _consolidate_campos_empresa(client, apartados, _track=_track)

    # Paso 5: extraer datos_aplicativo del contexto completo
    datos_aplicativo = _extract_datos_aplicativo(client, full_context, campos_empresa, _track=_track)

    root = {
        "version_esquema": "2.0",
        "convocatoria": {
            "nombre": conv_meta.get("nombre") or conv_name,
            "anio": conv_meta.get("anio"),
            "organismo": conv_meta.get("organismo") or "",
            "tipo_ayuda": conv_meta.get("tipo_ayuda") or "otro",
            "fecha_generacion": date.today().isoformat(),
        },
        "campos_empresa": campos_empresa,
        "apartados": apartados,
        "datos_aplicativo": datos_aplicativo,
    }

    return markdown, root


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
    incluir_evaluador: bool = False,
) -> str:
    # La instrucción del usuario se coloca SIEMPRE al final del prompt (máxima
    # recencia). Si se coloca antes del bloque de documentos, el volcado de
    # contexto la entierra y el modelo la ignora.
    instr_block = _instr_block(instrucciones)
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
        evaluador_block = f"INCLUIR_EVALUADOR: {'SI' if incluir_evaluador else 'NO'}"
        return (
            f"{modo_block}\n\n"
            f"{evaluador_block}\n\n"
            f"Documentos de la convocatoria '{conv_name}':\n\n{context}\n\n"
            f"Genera la landing page siguiendo las instrucciones del system prompt."
            f"{instr_block}"
        )
    else:
        return (
            f"A continuación tienes los documentos de la convocatoria procesados:\n\n{context}\n\n"
            f"Genera el entregable siguiendo las instrucciones del system prompt."
            f"{instr_block}"
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
        # Copia mutable de los entregables ya persistidos, para poder reutilizar un
        # CFG de evaluador generado en una salida anterior DE ESTE MISMO job (la
        # salida 3 corre antes que la 6 al ordenar por output_type, pero conv["entregables_json"]
        # es una foto fija de antes de empezar el job: no se actualiza sola).
        conv_entregables = dict(conv["entregables_json"])

        progress = {"outputs": {str(s["output_type"]): {"status": "queued"} for s in salida_requests}}
        db.update_job(job_id, "running", progress)

        for salida_req in sorted(salida_requests, key=lambda s: s["output_type"]):
            output_type = salida_req["output_type"]
            instrucciones = salida_req.get("instrucciones_adicionales", "")
            modo = salida_req.get("modo") or "ABIERTA"
            variante = salida_req.get("variante") or "A"
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

                    md_text, output_4_data = _generate_output_4(
                        client, conv_name, documents_json, instrucciones,
                        model=model, _track=track, _progress_cb=progress_cb,
                    )
                    generated["4"] = md_text
                    generated["4_json"] = json.dumps(output_4_data, ensure_ascii=False)

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
                    existing_cfg = _get_existing_cfg(conv_entregables)
                    html_6, cfg_used = _generate_output_6(
                        client, conv_name, context, instrucciones,
                        existing_cfg=existing_cfg, model=model, _track=track,
                    )
                    generated["6"] = html_6
                    generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)
                    conv_entregables["6_cfg"] = generated["6_cfg"]

                elif output_type == 3:
                    incluir_evaluador = bool(salida_req.get("incluir_evaluador", False))
                    existing_cfg = _get_existing_cfg(conv_entregables)
                    html_3, seo_3, cfg_used = _generate_output_3(
                        client, conv_name, context, instrucciones, modo, variante,
                        incluir_evaluador=incluir_evaluador, existing_cfg=existing_cfg,
                        model=model, _track=track,
                    )
                    generated["3"] = html_3
                    generated["3_seo"] = json.dumps(seo_3, ensure_ascii=False)
                    if cfg_used is not None:
                        generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)
                        conv_entregables["6_cfg"] = generated["6_cfg"]

                else:
                    user_prompt = _build_user_prompt(conv_name, context, output_type, instrucciones, modo)
                    generated[key] = _claude(
                        client, system=p.SYSTEM_PROMPTS[output_type], user=user_prompt,
                        max_tokens=p.MAX_TOKENS[output_type], model=model, _track=track,
                    )

                generated[f"{output_type}_instruccion"] = instrucciones
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
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
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


@app.get("/assets/logo.png")
def asset_logo():
    """Sirve el logo (versión blanca) para incrustarlo en el email de resultado."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "logo-negativo.png"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "logo-negativo.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo no encontrado.")


@app.get("/demo/inpyme-evaluador")
def demo_inpyme_evaluador():
    """
    Sirve el HTML standalone del autoevaluador INPYME como fichero estático.
    Se referencia por src del iframe en vez de incrustarlo en un <template> del
    HTML de WordPress: WordPress normaliza entidades sueltas ("&&" -> "&#038;&#038;")
    dentro de contenido no reconocido como <script> real, lo que rompía la
    sintaxis del evaluador. Sirviéndolo aquí, ese HTML nunca pasa por WordPress.
    """
    path = os.path.join(os.path.dirname(__file__), "static_demo", "inpyme-evaluador.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No encontrado.")
    return FileResponse(path, media_type="text/html; charset=utf-8")


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
    from datetime import datetime, timezone as tz
    if db.get_convocatoria(convocatoria_id) is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    if len(files) != len(etiquetas):
        raise HTTPException(status_code=422, detail="El número de archivos y etiquetas debe coincidir.")

    now = datetime.now(tz.utc).isoformat()
    documents, errors = [], []

    for file, etiqueta in zip(files, etiquetas):
        if etiqueta not in extractors.ORIGINAL_LABELS:
            errors.append(f"'{file.filename}': etiqueta '{etiqueta}' no válida.")
            continue
        content = await file.read()
        try:
            texto = extractors.extract_text(content, file.filename)
        except ValueError as exc:
            errors.append(f"'{file.filename}': {exc}")
            continue
        documents.append({
            "etiqueta": etiqueta,
            "nombre_archivo": file.filename,
            "texto": texto,
            "es_adicional": False,
            "fecha_subida": now,
        })

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


@app.post("/convocatorias/{convocatoria_id}/documentos/add")
async def add_additional_documents(
    convocatoria_id: int,
    files: Annotated[list[UploadFile], File(description="Documentos adicionales a añadir")],
    etiquetas: Annotated[list[str], Form(description="Etiqueta por cada archivo")],
):
    """Añade documentos adicionales a una convocatoria existente sin reemplazar los originales."""
    from datetime import datetime, timezone as tz
    if db.get_convocatoria(convocatoria_id) is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")
    if len(files) != len(etiquetas):
        raise HTTPException(status_code=422, detail="El número de archivos y etiquetas debe coincidir.")

    now = datetime.now(tz.utc).isoformat()
    documents, errors = [], []

    for file, etiqueta in zip(files, etiquetas):
        if not etiqueta.strip():
            errors.append(f"'{file.filename}': la etiqueta no puede estar vacía.")
            continue
        content = await file.read()
        try:
            texto = extractors.extract_text(content, file.filename)
        except ValueError as exc:
            errors.append(f"'{file.filename}': {exc}")
            continue
        documents.append({
            "etiqueta": etiqueta.strip(),
            "nombre_archivo": file.filename,
            "texto": texto,
            "es_adicional": True,
            "fecha_subida": now,
        })

    if errors and not documents:
        raise HTTPException(status_code=422, detail=errors)

    db.append_documentos(convocatoria_id, documents)

    response: dict = {
        "convocatoria_id": convocatoria_id,
        "documentos_añadidos": len(documents),
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
# Landing (salida 3): SEO editable + variante de distribución
# ---------------------------------------------------------------------------

def _load_landing_seo(convocatoria_id: int) -> tuple[dict, dict]:
    """
    Carga la metadata de la landing (3_seo) de una convocatoria ya generada.
    Devuelve (seo, entregables). Lanza HTTPException si no existe o falta el cuerpo.
    """
    conv = db.get_convocatoria(convocatoria_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada.")

    entregables = conv["entregables_json"]
    if "3_seo" not in entregables or "3" not in entregables:
        raise HTTPException(
            status_code=404,
            detail="La landing aún no se ha generado. Genérala antes de editarla.",
        )
    try:
        seo = json.loads(entregables["3_seo"])
    except Exception:
        seo = {}
    if not seo.get("body_html"):
        raise HTTPException(
            status_code=422,
            detail="No se conserva el cuerpo de la landing. Regenérala para poder editarla.",
        )
    return seo, entregables


def _public_seo(seo: dict) -> dict:
    """Subconjunto de la metadata de landing que se devuelve al frontend."""
    return {k: seo.get(k) for k in (
        "seo_title", "meta_description", "slug", "variant", "confirmed",
        "h1_recomendado", "keywords_principales", "faqs_sugeridas", "incluir_evaluador",
    )}


@app.post("/convocatorias/{convocatoria_id}/landing/seo")
def update_landing_seo(convocatoria_id: int, body: LandingSeoRequest):
    """
    Re-aplica los campos SEO editados a la landing ya generada SIN llamar a Claude.
    Reconstruye el HTML a partir del cuerpo guardado + el nuevo título y meta description,
    conservando la variante de distribución actual. El slug se guarda pero no va en el HTML.
    """
    seo, entregables = _load_landing_seo(convocatoria_id)
    body_html = seo["body_html"]
    variant = output3_template.normalize_variant(seo.get("variant", "A"))
    cfg = _get_existing_cfg(entregables) if seo.get("incluir_evaluador") else None

    seo_title = body.seo_title.strip()
    meta_description = body.meta_description.strip()
    slug = output3_template.slugify(body.slug) if body.slug.strip() else seo.get("slug", "")

    new_html = output3_template.build_output_3_html(body_html, slug, variant, cfg=cfg)
    new_seo = {
        **seo,
        "seo_title": seo_title,
        "meta_description": meta_description,
        "slug": slug,
        "body_html": body_html,
        "variant": variant,
        "confirmed": True,
    }
    db.update_entregables(convocatoria_id, {
        "3": new_html,
        "3_seo": json.dumps(new_seo, ensure_ascii=False),
    })
    return {"convocatoria_id": convocatoria_id, "seo": _public_seo(new_seo)}


@app.post("/convocatorias/{convocatoria_id}/landing/variant")
def update_landing_variant(convocatoria_id: int, body: LandingVariantRequest):
    """
    Cambia la variante de distribución (fondos por bloque) de la landing ya generada SIN
    llamar a Claude. Reconstruye el HTML a partir del cuerpo y el SEO guardados con la nueva
    variante. El contenido y el SEO no cambian.
    """
    seo, entregables = _load_landing_seo(convocatoria_id)
    variant = output3_template.normalize_variant(body.variante)
    cfg = _get_existing_cfg(entregables) if seo.get("incluir_evaluador") else None

    new_html = output3_template.build_output_3_html(
        seo["body_html"], seo.get("slug", ""), variant, cfg=cfg
    )
    new_seo = {**seo, "variant": variant}
    db.update_entregables(convocatoria_id, {
        "3": new_html,
        "3_seo": json.dumps(new_seo, ensure_ascii=False),
    })
    return {"convocatoria_id": convocatoria_id, "seo": _public_seo(new_seo)}


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
        variante = salida_req.variante or "A"
        model = pricing.MODEL_PER_OUTPUT.get(output_type, pricing.MODELS["sonnet"])
        track = _make_tracker(convocatoria_id, str(output_type))

        try:
            if output_type == 1:
                generated["1"] = _generate_output_1(
                    client, conv["nombre"], context, instrucciones,
                    model=model, _track=track,
                )

            elif output_type == 4:
                md_text, output_4_data = _generate_output_4(
                    client, conv["nombre"], conv["documentos_json"], instrucciones,
                    model=model, _track=track,
                )
                generated["4"] = md_text
                generated["4_json"] = json.dumps(output_4_data, ensure_ascii=False)

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
                existing_cfg = _get_existing_cfg(generated) or _get_existing_cfg(conv["entregables_json"])
                html_6, cfg_used = _generate_output_6(
                    client, conv["nombre"], context, instrucciones,
                    existing_cfg=existing_cfg, model=model, _track=track,
                )
                generated["6"] = html_6
                generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)

            elif output_type == 3:
                incluir_evaluador = bool(getattr(salida_req, "incluir_evaluador", False))
                existing_cfg = _get_existing_cfg(generated) or _get_existing_cfg(conv["entregables_json"])
                html_3, seo_3, cfg_used = _generate_output_3(
                    client, conv["nombre"], context, instrucciones, modo, variante,
                    incluir_evaluador=incluir_evaluador, existing_cfg=existing_cfg,
                    model=model, _track=track,
                )
                generated["3"] = html_3
                generated["3_seo"] = json.dumps(seo_3, ensure_ascii=False)
                if cfg_used is not None:
                    generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)

            else:
                user_prompt = _build_user_prompt(conv["nombre"], context, output_type, instrucciones, modo)
                generated[str(output_type)] = _claude(
                    client, system=p.SYSTEM_PROMPTS[output_type], user=user_prompt,
                    max_tokens=p.MAX_TOKENS[output_type], model=model, _track=track,
                )

            generated[f"{output_type}_instruccion"] = instrucciones

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
            variante = salida_req.variante or "A"
            model = pricing.MODEL_PER_OUTPUT.get(output_type, pricing.MODELS["sonnet"])
            track = _make_tracker(convocatoria_id, str(output_type))

            try:
                if output_type == 1:
                    generated["1"] = _generate_output_1(
                        client, conv["nombre"], context, instrucciones,
                        model=model, _track=track,
                    )

                elif output_type == 4:
                    md_text, output_4_data = _generate_output_4(
                        client, conv["nombre"], conv["documentos_json"], instrucciones,
                        model=model, _track=track,
                    )
                    generated["4"] = md_text
                    generated["4_json"] = json.dumps(output_4_data, ensure_ascii=False)

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
                    existing_cfg = _get_existing_cfg(generated) or _get_existing_cfg(conv["entregables_json"])
                    html_6, cfg_used = _generate_output_6(
                        client, conv["nombre"], context, instrucciones,
                        existing_cfg=existing_cfg, model=model, _track=track,
                    )
                    generated["6"] = html_6
                    generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)

                elif output_type == 3:
                    incluir_evaluador = bool(getattr(salida_req, "incluir_evaluador", False))
                    existing_cfg = _get_existing_cfg(generated) or _get_existing_cfg(conv["entregables_json"])
                    html_3, seo_3, cfg_used = _generate_output_3(
                        client, conv["nombre"], context, instrucciones, modo, variante,
                        incluir_evaluador=incluir_evaluador, existing_cfg=existing_cfg,
                        model=model, _track=track,
                    )
                    generated["3"] = html_3
                    generated["3_seo"] = json.dumps(seo_3, ensure_ascii=False)
                    if cfg_used is not None:
                        generated["6_cfg"] = json.dumps(cfg_used, ensure_ascii=False)

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
            except HTTPException as exc:
                yield _evt({"tipo": "error", "mensaje": str(exc.detail)})
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


# ---------------------------------------------------------------------------
# Send result email (called from evaluador HTML via Resend)
# ---------------------------------------------------------------------------

class ResultEmailRequest(BaseModel):
    nombre: str
    empresa: str
    email: str
    convocatoria: str
    puntuacion_actual: int = 0
    puntuacion_max: int = 0
    veredicto: str = ""


@app.post("/send-result-email")
def send_result_email(req: ResultEmailRequest):
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="Servicio de email no configurado.")

    backend_url = output6_template._get_backend_url()
    logo_url = f"{backend_url}/assets/logo.png" if backend_url else ""

    html = result_email.build_result_email_html(
        nombre=req.nombre,
        empresa=req.empresa,
        convocatoria=req.convocatoria,
        puntuacion_actual=req.puntuacion_actual,
        puntuacion_max=req.puntuacion_max,
        veredicto=req.veredicto,
        logo_url=logo_url,
    )

    try:
        resend.Emails.send({
            "from": "Innóvate 4.0 <hola@innovate40.es>",
            "to": [req.email],
            "subject": f"Tu resultado en {req.convocatoria} — Innóvate 4.0",
            "html": html,
        })
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error al enviar el email: {exc}")

    return {"ok": True}


# ---------------------------------------------------------------------------
# Submit evaluation (evaluador/cualificador embebido o standalone — vía Resend)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match((value or "").strip()))


class EvaluationLead(BaseModel):
    nombre: str = ""
    empresa: str = ""
    poblacion: str = ""
    telefono: str = ""
    email: str = ""
    website: str = ""  # honeypot oculto: debe llegar siempre vacío
    privacy: bool = False


class SubmitEvaluationRequest(BaseModel):
    source: str = ""
    tool: str = ""
    created_at: str = ""
    page_url: str = ""
    lead: EvaluationLead
    summary: list | dict = {}
    answers: dict = {}
    pending_actions: list = []
    legal_note: str = ""


@app.post("/submit-evaluation")
def submit_evaluation(req: SubmitEvaluationRequest):
    """
    Recibe el envío de un evaluador/cualificador de encaje: datos de contacto,
    respuestas completas y resultado calculado en el frontend. Envía dos
    emails por Resend (interno a Innóvate 4.0 + cliente) y devuelve
    {"success": true} SOLO si el email al cliente se ha enviado correctamente.
    El frontend no debe mostrar el resultado hasta recibir esa confirmación.
    """
    lead = req.lead

    # Honeypot: si el campo oculto viene relleno, es un envío automatizado.
    # Se responde con éxito sin enviar ningún email, para no delatar el filtro.
    if lead.website.strip():
        return {"success": True}

    if (
        not lead.nombre.strip()
        or not lead.empresa.strip()
        or not lead.telefono.strip()
        or not lead.email.strip()
        or not lead.privacy
    ):
        return JSONResponse(status_code=422, content={
            "success": False,
            "message": "Revisa los campos obligatorios antes de continuar.",
        })
    if not _is_valid_email(lead.email):
        return JSONResponse(status_code=422, content={
            "success": False,
            "message": "Introduce un correo electrónico válido.",
        })

    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return JSONResponse(status_code=503, content={
            "success": False,
            "message": "No hemos podido enviar la evaluación en este momento. "
                       "Inténtalo de nuevo o contacta directamente con Innóvate 4.0.",
        })

    from_email = os.environ.get("RESEND_FROM_EMAIL", "Innóvate 4.0 <hola@innovate40.es>")
    reply_to = os.environ.get("EVALUATOR_REPLY_TO_EMAIL", "")
    internal_email = os.environ.get("EVALUATOR_INTERNAL_EMAIL", "")

    backend_url = output6_template._get_backend_url()
    logo_url = f"{backend_url}/assets/logo.png" if backend_url else ""

    tool = req.tool or req.source or "la ayuda"
    lead_dict = lead.model_dump()

    # Email interno — best effort: si falla, se registra pero no bloquea al usuario.
    if internal_email:
        try:
            resend.Emails.send({
                "from": from_email,
                "to": [internal_email],
                **({"reply_to": [reply_to]} if reply_to else {}),
                "subject": f"Nuevo resultado de cualificador - {tool} - {lead.empresa}",
                "html": result_email.build_internal_lead_email_html(
                    tool=tool,
                    source=req.source,
                    page_url=req.page_url,
                    created_at=req.created_at,
                    lead=lead_dict,
                    summary=req.summary,
                    answers=req.answers,
                    pending_actions=req.pending_actions,
                    logo_url=logo_url,
                ),
            })
        except Exception as exc:
            print(f"[submit-evaluation] Error enviando email interno: {exc}")

    # Email al cliente — este sí debe llegar para poder mostrar el resultado.
    try:
        resend.Emails.send({
            "from": from_email,
            "to": [lead.email],
            **({"reply_to": [reply_to]} if reply_to else {}),
            "subject": f"Resultado de tu evaluación para {tool}",
            "html": result_email.build_user_lead_email_html(
                tool=tool,
                lead=lead_dict,
                summary=req.summary,
                logo_url=logo_url,
            ),
        })
    except Exception as exc:
        print(f"[submit-evaluation] Error enviando email al cliente: {exc}")
        return JSONResponse(status_code=502, content={
            "success": False,
            "message": "No hemos podido enviar la evaluación en este momento. "
                       "Inténtalo de nuevo o contacta directamente con Innóvate 4.0.",
        })

    return {"success": True}
