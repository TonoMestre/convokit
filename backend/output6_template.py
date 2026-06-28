"""
ConvoKit — Builder para la Salida 6 (Evaluador de encaje interactivo).

Flujo de generación:
1. Claude genera exclusivamente el objeto CFG como JSON.
2. build_output_6_html(config) inyecta ese JSON en la plantilla estática
   evaluador_template.html, que contiene todo el CSS y JS sin tocar.

Los placeholders del template son:
  {{CFG_JSON}}          — el objeto de configuración serializado
  {{TITULO_EVALUADOR}}  — el título de la página (<title>)
  {{LOGO_SRC}}          — data URI base64 del logo (para compatibilidad con iframe srcDoc)
  {{BACKEND_URL}}       — URL del backend de ConvoKit (para enviar el email de resultado)
"""

import base64
import json
import os
import pathlib

_TEMPLATE_PATH = pathlib.Path(__file__).parent / "evaluador_template.html"


def _load_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _load_logo_b64() -> str:
    candidates = [
        pathlib.Path(__file__).parent.parent / "frontend" / "public" / "logo-negativo.png",
        pathlib.Path(__file__).parent / "logo-negativo.png",
    ]
    for p in candidates:
        if p.exists():
            return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return "/logo-negativo.png"


def _get_backend_url() -> str:
    url = os.environ.get("BACKEND_URL", "").rstrip("/")
    return url


def build_output_6_html(config: dict) -> str:
    """
    Inyecta el objeto CFG en la plantilla estática y devuelve el HTML completo.
    El JSON se escapa con ensure_ascii=False; los caracteres </ se protegen para
    evitar el cierre prematuro del tag <script>.
    """
    titulo = config.get("textos", {}).get("titulo_evaluador", "Evaluador de encaje")
    config_json = json.dumps(config, ensure_ascii=False, indent=2)
    config_json = config_json.replace("</", "<\\/")

    html = _load_template()
    html = html.replace("{{CFG_JSON}}", config_json)
    html = html.replace("{{TITULO_EVALUADOR}}", titulo)
    html = html.replace("{{LOGO_SRC}}", _load_logo_b64())
    html = html.replace("{{BACKEND_URL}}", _get_backend_url())
    return html
