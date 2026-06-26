"""
ConvoKit — exportación de salidas 4 y 5 a JSON estructurado.

Valida y normaliza los arrays JSON almacenados en SQLite antes de
devolverlos al frontend para su descarga.

Esquemas (PRD v2.2, sección 12):

  Salida 4 — secciones de la memoria:
    [{ "codigo", "nombre", "puntos_max", "inputs_minimos",
       "inputs_puntuacion_completa", "documentos_requeridos", "prompt" }]

  Salida 5 — lista de documentación:
    [{ "documento", "obligatorio", "modelo_oficial", "ambito", "vigencia" }]
"""

from __future__ import annotations

import json


def _parse(raw: str | None) -> list:
    """Parsea el campo JSON de la BD; devuelve lista vacía si falla."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def export_output_4(raw_json: str | None) -> list[dict]:
    """
    Normaliza y devuelve el array de secciones de la memoria (salida 4).
    Garantiza que todos los campos obligatorios del esquema PRD están presentes.
    """
    items = _parse(raw_json)
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append({
            "codigo": item.get("codigo") or "",
            "nombre": item.get("nombre") or "",
            "puntos_max": item.get("puntos_max"),
            "inputs_minimos": item.get("inputs_minimos") or [],
            "inputs_puntuacion_completa": item.get("inputs_puntuacion_completa") or [],
            "documentos_requeridos": item.get("documentos_requeridos") or [],
            "prompt": item.get("prompt") or "",
        })
    return result


def export_output_5(raw_json: str | None) -> list[dict]:
    """
    Normaliza y devuelve el array de documentación requerida (salida 5).
    Garantiza que todos los campos obligatorios del esquema PRD están presentes.
    """
    items = _parse(raw_json)
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
