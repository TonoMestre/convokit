"""
ConvoKit — exportación de salidas 4 y 5 a JSON estructurado.

Valida y normaliza los datos JSON almacenados en SQLite antes de
devolverlos al frontend para su descarga.

Esquemas:

  Salida 4 — contrato de exportación v2.5 (docs/contrato-convokit.md).
  La raíz es un OBJETO, no un array:
    {
      "version_esquema": "2.5",
      "convocatoria": {"nombre", "anio", "organismo", "tipo_ayuda", "fecha_generacion"},
      "campos_empresa": [{"id", "nombre", "descripcion", "formato", ...}],
      "campos_proyecto": [{"id", "nombre", "descripcion", "formato", ...}],
      "apartados": [{
        "codigo", "nombre", "puntos_max", "prompt", "contexto_evaluador"?,
        "requiere_calculo_rentabilidad", "usa_tabla_inversiones",
        "inputs": [{"id", "label", "tipo", "nivel", "ayuda"?,
                    "ref_campo_empresa"?, "ref_campo_proyecto"?}],
        "documentos_requeridos": [{"nombre", "fuente"}],
      }],
      "tres_ofertas": {"umbral", "exencion_gasto_antes_resolucion", "condiciones_exencion"},
      "parametros_convocatoria": [{"id", "label", "valor", "unidad"?, "nota"?}],
      "documentos_convocatoria": [{"nombre", "fuente", "obligatorio", "nota"?}],
      "datos_aplicativo": [{"id", "label", "tipo_dato", "ambito", "obligatorio", "opciones"?}
                           | {"ref_campo_proyecto", "obligatorio"}],
    }

  Salida 5 — lista de documentación:
    [{ "documento", "obligatorio", "modelo_oficial", "ambito", "vigencia" }]
"""

from __future__ import annotations

import json
import re
import unicodedata

# Lista negra de placeholders prohibidos por el contrato (nunca se exportan como
# ítem real): "no aplica", "ya incluido", "ver otro apartado", "ya las tienes", "n/a"...
_PLACEHOLDER_BLACKLIST = {
    "no aplica", "n/a", "na", "ninguno", "ninguna", "ninguno.", "ninguna.",
    "ya incluido", "ya incluida", "ya incluido.", "ya incluida.",
    "ver otro apartado", "ya las tienes", "ya las tienes.",
}

_INPUT_TIPOS = {"texto_libre", "dato_empresa", "dato_proyecto", "inversion", "rentabilidad", "documento"}
_NIVELES = {"minimo", "completo"}
_DOC_FUENTES = {"cliente", "perfil_estrategico", "generado"}
_CAMPO_FORMATOS = {"texto", "tabla_historica", "numero"}
_TIPOS_AYUDA = {
    "inversion_productiva", "digitalizacion", "idi", "internacionalizacion",
    "medioambiente_energia", "empleo", "otro",
}
_TIPOS_DATO = {"texto_corto", "numero", "booleano", "fecha", "url", "seleccion"}
_AMBITOS = {"empresa", "proyecto"}


def _is_placeholder(text: str) -> bool:
    return (text or "").strip().lower() in _PLACEHOLDER_BLACKLIST


def _ascii_slug(value: str) -> str:
    """Fuerza ids kebab-case solo ASCII (contrato v2.2, regla 11):
    'experiencia-minima-años' -> 'experiencia-minima-anios' (ñ->n via NFKD)."""
    if not value:
        return value
    # ñ -> ni sigue la convención del contrato ("años" -> "anios"), no la NFKD ("anos")
    value = value.replace("ñ", "ni").replace("Ñ", "NI")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return ascii_text or value


# Contrato v2.2, checklist punto 6: prohibido incrustar cifras de las bases en un
# label ("(máximo 70%)", "(hasta 15.000 euros)"). El tope va como su propio
# parámetro en parametros_convocatoria; aquí se limpia el label de forma
# conservadora: solo paréntesis que empiezan por una palabra de límite Y
# contienen un dígito.
_LABEL_LIMIT_RE = re.compile(
    r"\s*\((?:m[aá]x(?:imo|\.)?|m[ií]n(?:imo|\.)?|hasta|tope|l[ií]mite)[^)]*\d[^)]*\)",
    re.IGNORECASE,
)


def _strip_embedded_limits(label: str) -> str:
    return _LABEL_LIMIT_RE.sub("", label or "").strip()


def _parse(raw: str | None, default):
    """Parsea un campo JSON de la BD; devuelve `default` si falta o es inválido."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _normalize_input(item: dict, campo_ids: set[str], campo_proyecto_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    label = _strip_embedded_limits(item.get("label") or "")
    if not label or _is_placeholder(label):
        return None
    tipo = item.get("tipo") if item.get("tipo") in _INPUT_TIPOS else "texto_libre"
    nivel = item.get("nivel") if item.get("nivel") in _NIVELES else "minimo"
    normalized = {
        "id": _ascii_slug(item.get("id") or ""),
        "label": label,
        "tipo": tipo,
        "nivel": nivel,
    }
    if item.get("ayuda"):
        normalized["ayuda"] = item["ayuda"]
    if tipo == "dato_empresa":
        ref = _ascii_slug(item.get("ref_campo_empresa") or "")
        if ref and ref in campo_ids:
            normalized["ref_campo_empresa"] = ref
    elif tipo == "dato_proyecto":
        ref = _ascii_slug(item.get("ref_campo_proyecto") or "")
        if ref and ref in campo_proyecto_ids:
            normalized["ref_campo_proyecto"] = ref
        else:
            # dato_proyecto sin ref valido incumple el contrato (MemorAI lo
            # rechazaria); se degrada a texto_libre.
            normalized["tipo"] = "texto_libre"
    return normalized


def _normalize_documento_requerido(doc) -> dict | None:
    if isinstance(doc, dict):
        nombre = doc.get("nombre") or ""
        fuente = doc.get("fuente") if doc.get("fuente") in _DOC_FUENTES else "cliente"
    elif isinstance(doc, str):
        nombre, fuente = doc, "cliente"
    else:
        return None
    if not nombre or _is_placeholder(nombre):
        return None
    return {"nombre": nombre, "fuente": fuente}


def _normalize_apartado(item: dict, campo_ids: set[str], campo_proyecto_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    codigo = item.get("codigo") or ""
    if not codigo:
        return None
    inputs = [
        n for n in (
            _normalize_input(x, campo_ids, campo_proyecto_ids)
            for x in (item.get("inputs") or [])
        ) if n
    ]
    docs = [n for n in (_normalize_documento_requerido(x) for x in (item.get("documentos_requeridos") or [])) if n]
    normalized = {
        "codigo": codigo,
        "nombre": item.get("nombre") or "",
        "puntos_max": item.get("puntos_max"),
        "prompt": item.get("prompt") or "",
        "requiere_calculo_rentabilidad": bool(item.get("requiere_calculo_rentabilidad", False)),
        "usa_tabla_inversiones": bool(item.get("usa_tabla_inversiones", False)),
        "inputs": inputs,
        "documentos_requeridos": docs,
    }
    # Contrato v2.4, regla 15: opcional, solo si viene informado (nunca cadena vacía).
    contexto_evaluador = (item.get("contexto_evaluador") or "").strip()
    if contexto_evaluador:
        normalized["contexto_evaluador"] = contexto_evaluador
    return normalized


def _normalize_campo_empresa(item: dict) -> dict | None:
    if not isinstance(item, dict) or not item.get("id"):
        return None
    formato = item.get("formato") if item.get("formato") in _CAMPO_FORMATOS else "texto"
    campo = {
        "id": _ascii_slug(item["id"]),
        "nombre": item.get("nombre") or "",
        "descripcion": item.get("descripcion") or "",
        "formato": formato,
    }
    if formato == "tabla_historica":
        campo["variables"] = item.get("variables") or []
        campo["num_anios"] = item.get("num_anios")
    return campo


def _normalize_dato_aplicativo(item: dict, campo_proyecto_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None

    # Entrada por referencia a campos_proyecto (dato pedido tambien en la memoria):
    # no redefine label/tipo_dato, solo apunta al catalogo.
    ref = _ascii_slug(item.get("ref_campo_proyecto") or "")
    if ref:
        if ref not in campo_proyecto_ids:
            return None
        return {"ref_campo_proyecto": ref, "obligatorio": bool(item.get("obligatorio", False))}

    label = _strip_embedded_limits(item.get("label") or "")
    if not label or _is_placeholder(label):
        return None
    tipo_dato = item.get("tipo_dato") if item.get("tipo_dato") in _TIPOS_DATO else "texto_corto"
    ambito = item.get("ambito") if item.get("ambito") in _AMBITOS else "proyecto"
    normalized = {
        "id": _ascii_slug(item.get("id") or ""),
        "label": label,
        "tipo_dato": tipo_dato,
        "ambito": ambito,
        "obligatorio": bool(item.get("obligatorio", False)),
    }
    if tipo_dato == "seleccion":
        opciones = item.get("opciones")
        normalized["opciones"] = opciones if isinstance(opciones, list) else []
    return normalized


def _normalize_documento_convocatoria(item: dict) -> dict | None:
    """Documento exigido para CUALQUIER solicitud de la convocatoria (contrato v2.4),
    independiente de cualquier apartado concreto — distinto de documentos_requeridos
    (que es por apartado)."""
    if not isinstance(item, dict):
        return None
    nombre = item.get("nombre") or ""
    if not nombre or _is_placeholder(nombre):
        return None
    fuente = item.get("fuente") if item.get("fuente") in _DOC_FUENTES else "cliente"
    normalized = {
        "nombre": nombre,
        "fuente": fuente,
        "obligatorio": bool(item.get("obligatorio", False)),
    }
    if item.get("nota"):
        normalized["nota"] = item["nota"]
    return normalized


def _normalize_tres_ofertas(item) -> dict:
    """Bloque obligatorio del contrato v2.1. Umbral numérico o null, nunca string."""
    if not isinstance(item, dict):
        item = {}
    umbral = item.get("umbral")
    if isinstance(umbral, str):
        try:
            umbral = float(umbral.replace(".", "").replace(",", "."))
        except ValueError:
            umbral = None
    if isinstance(umbral, float) and umbral.is_integer():
        umbral = int(umbral)
    if not isinstance(umbral, (int, float)):
        umbral = None
    exencion = bool(item.get("exencion_gasto_antes_resolucion", False))
    return {
        "umbral": umbral,
        "exencion_gasto_antes_resolucion": exencion,
        "condiciones_exencion": (item.get("condiciones_exencion") or "") if exencion else "",
    }


def _normalize_parametro(item: dict) -> dict | None:
    """Parámetro de convocatoria: constante de las bases, siempre con valor."""
    if not isinstance(item, dict):
        return None
    label = item.get("label") or ""
    valor = item.get("valor")
    if not label or _is_placeholder(label) or valor is None or valor == "":
        return None
    normalized = {
        "id": _ascii_slug(item.get("id") or ""),
        "label": label,
        "valor": valor,
    }
    if item.get("unidad"):
        normalized["unidad"] = item["unidad"]
    if item.get("nota"):
        normalized["nota"] = item["nota"]
    return normalized


def _drop_parent_apartados(apartados: list[dict]) -> list[dict]:
    """Red de seguridad de la regla 1bis: elimina bloques padre emitidos junto a sus
    subapartados (ej. "I" cuando existen "I.A", "I.B")."""
    codigos = [a["codigo"] for a in apartados]

    def is_parent(codigo: str) -> bool:
        return any(
            other != codigo and other.startswith(codigo)
            and len(other) > len(codigo) and not other[len(codigo)].isalnum()
            for other in codigos
        )

    return [a for a in apartados if not is_parent(a["codigo"])]


def _dedupe_codigos(apartados: list[dict]) -> None:
    """Red de seguridad: desambigua códigos repetidos que hayan llegado a la BD sin pasar
    por la desambiguación de main.py (ej. entregables antiguos regenerados a mano)."""
    seen: dict[str, int] = {}
    for apartado in apartados:
        codigo = apartado["codigo"]
        count = seen.get(codigo, 0)
        seen[codigo] = count + 1
        if count > 0:
            apartado["codigo"] = f"{codigo}-{count + 1}"


def export_output_4(raw_json: str | None) -> dict:
    """
    Normaliza y devuelve el objeto raíz de la salida 4 (contrato v2.5).
    Garantiza vocabularios cerrados, ids solo ASCII, apartados solo hoja,
    labels sin cifras de las bases incrustadas, descarta placeholders de la
    lista negra, elimina referencias huérfanas a campos_empresa y
    campos_proyecto, deduplica datos_aplicativo contra ambos catálogos y
    colapsa sus duplicados internos (dos entradas con el mismo id, o dos
    referencias al mismo campo del catálogo — contrato v2.5, corrección 3).
    """
    data = _parse(raw_json, {})
    if not isinstance(data, dict):
        data = {}

    conv = data.get("convocatoria") or {}
    tipo_ayuda = conv.get("tipo_ayuda") if conv.get("tipo_ayuda") in _TIPOS_AYUDA else "otro"
    convocatoria = {
        "nombre": conv.get("nombre") or "",
        "anio": conv.get("anio"),
        "organismo": conv.get("organismo") or "",
        "tipo_ayuda": tipo_ayuda,
        "fecha_generacion": conv.get("fecha_generacion") or "",
    }

    campos_empresa = [
        n for n in (_normalize_campo_empresa(c) for c in (data.get("campos_empresa") or [])) if n
    ]
    campo_ids = {c["id"] for c in campos_empresa}

    # campos_proyecto usa el mismo esquema que campos_empresa
    campos_proyecto = [
        n for n in (_normalize_campo_empresa(c) for c in (data.get("campos_proyecto") or [])) if n
    ]
    campo_proyecto_ids = {c["id"] for c in campos_proyecto}

    apartados = [
        n for n in (
            _normalize_apartado(a, campo_ids, campo_proyecto_ids)
            for a in (data.get("apartados") or [])
        ) if n
    ]
    apartados = _drop_parent_apartados(apartados)
    _dedupe_codigos(apartados)

    # No duplicar entre datos_aplicativo y memoria: si el id ya existe en el
    # catálogo de campos_empresa, el dato ya está cubierto como dato_empresa.
    # (Las entradas por referencia a campos_proyecto no llevan "id" propio.)
    datos_aplicativo = [
        n for n in (
            _normalize_dato_aplicativo(d, campo_proyecto_ids)
            for d in (data.get("datos_aplicativo") or [])
        )
        if n and n.get("id") not in campo_ids
    ]

    # Contrato v2.5, corrección 3 (red de seguridad determinista): colapsar
    # duplicados internos de datos_aplicativo — dos entradas con el mismo id,
    # o dos referencias al mismo campo del catálogo (el caso real S3-CV llegó
    # triplicado). Se conserva la primera aparición con el obligatorio más
    # restrictivo.
    seen_ids: dict[str, dict] = {}
    seen_refs: dict[str, dict] = {}
    deduped: list[dict] = []
    for dato in datos_aplicativo:
        ref = dato.get("ref_campo_proyecto")
        key_map = seen_refs if ref else seen_ids
        key = ref or dato.get("id")
        if key and key in key_map:
            key_map[key]["obligatorio"] = (
                key_map[key].get("obligatorio", False) or dato.get("obligatorio", False)
            )
            continue
        if key:
            key_map[key] = dato
        deduped.append(dato)
    datos_aplicativo = deduped

    parametros_convocatoria = [
        n for n in (_normalize_parametro(x) for x in (data.get("parametros_convocatoria") or [])) if n
    ]

    documentos_convocatoria = [
        n for n in (
            _normalize_documento_convocatoria(x) for x in (data.get("documentos_convocatoria") or [])
        ) if n
    ]

    return {
        "version_esquema": "2.5",
        "convocatoria": convocatoria,
        "campos_empresa": campos_empresa,
        "campos_proyecto": campos_proyecto,
        "apartados": apartados,
        "tres_ofertas": _normalize_tres_ofertas(data.get("tres_ofertas")),
        "parametros_convocatoria": parametros_convocatoria,
        "documentos_convocatoria": documentos_convocatoria,
        "datos_aplicativo": datos_aplicativo,
    }


def export_output_5(raw_json: str | None) -> list[dict]:
    """
    Normaliza y devuelve el array de documentación requerida (salida 5).
    Garantiza que todos los campos obligatorios del esquema PRD están presentes.
    """
    items = _parse(raw_json, [])
    if not isinstance(items, list):
        items = []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append({
            "documento": item.get("documento") or "",
            "obligatorio": bool(item.get("obligatorio", True)),
            "modelo_oficial": item.get("modelo_oficial") or "formato libre",
            "ambito": item.get("ambito") or "",
            "vigencia": item.get("vigencia"),
        })
    return result
