"""
ConvoKit — Builder para la Salida 6 (Evaluador de encaje interactivo).

Flujo de generación:
1. Claude genera exclusivamente el objeto CFG como JSON.
2. build_output_6_html(config) inyecta ese JSON en el fragmento reutilizable
   evaluador_core.html (CSS scoped bajo .evaluador-widget + markup + JS) y lo
   envuelve en una página completa independiente (doctype/html/head/body).

El mismo fragmento (evaluador_core.html) también lo usa output3_template.py
vía build_output_6_embed_fragment() para embeber el evaluador dentro de una
landing, sin duplicar el motor JS/CSS en dos sitios.

Los placeholders del fragmento son:
  {{CFG_JSON}}          — el objeto de configuración serializado
  {{LOGO_SRC}}          — data URI base64 del logo (para compatibilidad con iframe srcDoc)
  {{BACKEND_URL}}       — URL del backend de ConvoKit (para enviar los resultados)
"""

import base64
import json
import os
import pathlib

_CORE_PATH = pathlib.Path(__file__).parent / "evaluador_core.html"

_STANDALONE_SHELL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{titulo}</title>
<style>
  /* Esta página es un documento propio (no un fragmento embebido en otra
     página), así que aquí sí podemos resetear html/body: sin este reset
     el margin por defecto del user-agent (~8px) deja un marco en blanco
     alrededor del fondo crema del widget. */
  html, body {{ margin: 0; padding: 0; }}
</style>
</head>
<body>
{core}
</body>
</html>
"""


def _load_core() -> str:
    return _CORE_PATH.read_text(encoding="utf-8")


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
    if not url:
        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
        if domain:
            url = f"https://{domain}"
    return url


def _build_core(config: dict) -> str:
    """
    Inyecta el objeto CFG en el fragmento del evaluador. El JSON se escapa con
    ensure_ascii=False; los caracteres </ se protegen para evitar el cierre
    prematuro del tag <script>.
    """
    config_json = json.dumps(config, ensure_ascii=False, indent=2)
    config_json = config_json.replace("</", "<\\/")

    core = _load_core()
    core = core.replace("{{CFG_JSON}}", config_json)
    core = core.replace("{{LOGO_SRC}}", _load_logo_b64())
    core = core.replace("{{BACKEND_URL}}", _get_backend_url())
    return core


def build_output_6_html(config: dict) -> str:
    """Devuelve la página completa e independiente del evaluador (salida 6)."""
    titulo = config.get("textos", {}).get("titulo_evaluador", "Evaluador de encaje")
    core = _build_core(config)
    return _STANDALONE_SHELL.format(titulo=titulo, core=core)


def build_output_6_embed_fragment(config: dict) -> str:
    """
    Devuelve solo el fragmento del evaluador (sin doctype/html/head/body), para
    insertarlo dentro de otra página (la landing de la salida 3).
    """
    return _build_core(config)
