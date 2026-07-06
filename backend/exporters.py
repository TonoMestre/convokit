"""
ConvoKit — exportación de salidas 4 y 5 a JSON estructurado.

Valida y normaliza los datos JSON almacenados en SQLite antes de
devolverlos al frontend para su descarga.

Esquemas:

  Salida 4 — contrato de exportación v2.0 (docs/contrato-convokit.md).
  La raíz es un OBJETO, no un array:
    {
      "version_esquema": "2.0",
      "convocatoria": {"nombre", "anio", "organismo", "tipo_ayuda", "fecha_generacion"},
      "campos_empresa": [{"id", "nombre", "descripcion", "formato", ...}],
      "apartados": [{
        "codigo", "nombre", "puntos_max", "prompt",
        "requiere_calculo_rentabilidad", "usa_tabla_inversiones",
        "inputs": [{"id", "label", "tipo", "nivel", "ayuda"?, "ref_campo_empresa"?}],
        "documentos_requeridos": [{"nombre", "fuente"}],
      }],
      "datos_aplicativo": [{"id", "label", "tipo_dato", "ambito", "obligatorio", "opciones"?}],
    }

  Salida 5 — lista de documentación:
    [{ "documento", "obligatorio", "modelo_oficial", "ambito", "vigencia" }]
"""

from __future__ import annotations

import json

# Lista negra de placeholders prohibidos por el contrato (nunca se exportan como
# ítem real): "no aplica", "ya incluido", "ver otro apartado", "ya las tienes", "n/a"...
_PLACEHOLDER_BLACKLIST = {
    "no aplica", "n/a", "na", "ninguno", "ninguna", "ninguno.", "ninguna.",
    "ya incluido", "ya incluida", "ya incluido.", "ya incluida.",
    "ver otro apartado", "ya las tienes", "ya las tienes.",
}

_INPUT_TIPOS = {"texto_libre", "dato_empresa", "inversion", "rentabilidad", "documento"}
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


def _parse(raw: str | None, default):
    """Parsea un campo JSON de la BD; devuelve `default` si falta o es inválido."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _normalize_input(item: dict, campo_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    label = item.get("label") or ""
    if not label or _is_placeholder(label):
        return None
    tipo = item.get("tipo") if item.get("tipo") in _INPUT_TIPOS else "texto_libre"
    nivel = item.get("nivel") if item.get("nivel") in _NIVELES else "minimo"
    normalized = {
        "id": item.get("id") or "",
        "label": label,
        "tipo": tipo,
        "nivel": nivel,
    }
    if item.get("ayuda"):
        normalized["ayuda"] = item["ayuda"]
    if tipo == "dato_empresa":
        ref = item.get("ref_campo_empresa")
        if ref and ref in campo_ids:
            normalized["ref_campo_empresa"] = ref
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


def _normalize_apartado(item: dict, campo_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    codigo = item.get("codigo") or ""
    if not codigo:
        return None
    inputs = [n for n in (_normalize_input(x, campo_ids) for x in (item.get("inputs") or [])) if n]
    docs = [n for n in (_normalize_documento_requerido(x) for x in (item.get("documentos_requeridos") or [])) if n]
    return {
        "codigo": codigo,
        "nombre": item.get("nombre") or "",
        "puntos_max": item.get("puntos_max"),
        "prompt": item.get("prompt") or "",
        "requiere_calculo_rentabilidad": bool(item.get("requiere_calculo_rentabilidad", False)),
        "usa_tabla_inversiones": bool(item.get("usa_tabla_inversiones", False)),
        "inputs": inputs,
        "documentos_requeridos": docs,
    }


def _normalize_campo_empresa(item: dict) -> dict | None:
    if not isinstance(item, dict) or not item.get("id"):
        return None
    formato = item.get("formato") if item.get("formato") in _CAMPO_FORMATOS else "texto"
    campo = {
        "id": item["id"],
        "nombre": item.get("nombre") or "",
        "descripcion": item.get("descripcion") or "",
        "formato": formato,
    }
    if formato == "tabla_historica":
        campo["variables"] = item.get("variables") or []
        campo["num_anios"] = item.get("num_anios")
    return campo


def _normalize_dato_aplicativo(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    label = item.get("label") or ""
    if not label or _is_placeholder(label):
        return None
    tipo_dato = item.get("tipo_dato") if item.get("tipo_dato") in _TIPOS_DATO else "texto_corto"
    ambito = item.get("ambito") if item.get("ambito") in _AMBITOS else "proyecto"
    normalized = {
        "id": item.get("id") or "",
        "label": label,
        "tipo_dato": tipo_dato,
        "ambito": ambito,
        "obligatorio": bool(item.get("obligatorio", False)),
    }
    if tipo_dato == "seleccion":
        opciones = item.get("opciones")
        normalized["opciones"] = opciones if isinstance(opciones, list) else []
    return normalized


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
    Normaliza y devuelve el objeto raíz de la salida 4 (contrato v2.0).
    Garantiza vocabularios cerrados, descarta placeholders de la lista negra
    y elimina referencias huérfanas a campos_empresa.
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

    apartados = [
        n for n in (_normalize_apartado(a, campo_ids) for a in (data.get("apartados") or [])) if n
    ]
    _dedupe_codigos(apartados)

    datos_aplicativo = [
        n for n in (_normalize_dato_aplicativo(d) for d in (data.get("datos_aplicativo") or [])) if n
    ]

    return {
        "version_esquema": "2.0",
        "convocatoria": convocatoria,
        "campos_empresa": campos_empresa,
        "apartados": apartados,
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
