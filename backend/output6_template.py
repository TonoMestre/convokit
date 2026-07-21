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

Los placeholders del fragmento core son:
  {{CFG_JSON}}          — el objeto de configuración serializado
  {{BACKEND_URL}}       — URL del backend de ConvoKit (para enviar los resultados)

El core NO lleva header ni footer (embebido, la web contenedora ya los aporta);
solo el shell standalone los añade (tokens __TITULO__, __LOGO__, __CORE__).
"""

import base64
import json
import os
import pathlib

_CORE_PATH = pathlib.Path(__file__).parent / "evaluador_core.html"

# El shell standalone es un documento propio: aquí sí hay reset de html/body y
# cabecera/pie con logo y enlaces legales. El core NO los lleva (embebido dentro
# de la landing o de una página de WordPress, la web contenedora ya aporta los
# suyos), así que solo existen en esta salida standalone. El topbar fino del core
# se oculta aquí para no duplicar el rótulo "Evaluador de encaje" del header.
_STANDALONE_SHELL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITULO__</title>
<style>
  html, body { margin: 0; padding: 0; }
  body { display: flex; flex-direction: column; min-height: 100vh; background: #F4F4F6; }
  .shell-header {
    background: #1B2060;
    border-bottom: 2px solid #BE0034;
    padding: 16px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 10px rgba(0,0,0,.15);
  }
  .shell-header img { display: block; height: 28px; object-fit: contain; }
  .shell-header .shell-header-tag {
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    color: rgba(255,255,255,0.55);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .shell-main { flex: 1; display: flex; flex-direction: column; }
  .shell-main .evaluador-widget { flex: 1; }
  /* El core escopa con #i40-evaluador (1,1,0); para ganarle hay que igualar
     o superar esa especificidad, y el estilo del core va después en el documento. */
  .shell-main #i40-evaluador .widget-topbar { display: none; }
  .shell-footer {
    background: #1B2060;
    color: rgba(255,255,255,0.55);
    text-align: center;
    padding: 18px 24px;
    font-size: 0.75rem;
    line-height: 1.8;
    font-family: 'Inter', sans-serif;
  }
  .shell-footer a { color: rgba(255,255,255,0.55); }
  .shell-footer a:hover { color: #FFFFFF; }
</style>
</head>
<body>
<header class="shell-header">
  <img src="__LOGO__" alt="Innóvate 4.0" />
  <span class="shell-header-tag">Evaluador de encaje</span>
</header>
<main class="shell-main">
__CORE__
</main>
<footer class="shell-footer">
  © Innóvate 4.0 Estrategia Empresarial, S.L. &nbsp;|&nbsp;
  <a href="https://innovate40.es/aviso-legal/" target="_blank" rel="noopener noreferrer">Aviso legal</a>
  &nbsp;|&nbsp;
  <a href="mailto:proyectos2@innovate40.es">proyectos2@innovate40.es</a>
  &nbsp;|&nbsp; 960 66 66 10
</footer>
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
    core = core.replace("{{BACKEND_URL}}", _get_backend_url())
    return core


def build_output_6_html(config: dict) -> str:
    """Devuelve la página completa e independiente del evaluador (salida 6)."""
    titulo = config.get("textos", {}).get("titulo_evaluador", "Evaluador de encaje")
    core = _build_core(config)
    html = _STANDALONE_SHELL
    html = html.replace("__TITULO__", titulo)
    html = html.replace("__LOGO__", _load_logo_b64())
    html = html.replace("__CORE__", core)
    return html


def build_output_6_embed_fragment(config: dict) -> str:
    """
    Devuelve solo el fragmento del evaluador (sin doctype/html/head/body), para
    insertarlo dentro de otra página (la landing de la salida 3).
    """
    return _build_core(config)
