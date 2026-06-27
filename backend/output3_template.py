"""
ConvoKit — Builder para la Salida 3 (Landing page HTML).

Flujo de generación:
1. Claude genera SOLO el cuerpo HTML de la landing (las secciones <section>...),
   usando las clases CSS documentadas. Sin <html>, <head>, <style> ni <body>.
2. build_output_3_html(body_html, titulo) lo envuelve en la plantilla estática
   landing_template.html, que contiene el <head>, el CSS de marca, la cabecera y el pie.

El HTML resultante es completamente autocontenido y desplegable: se puede subir tal cual
a innovate40.es como subcarpeta. El formulario usa Web3Forms con POST plano (sin JS).
"""

import base64
import pathlib
import re

_TEMPLATE_PATH = pathlib.Path(__file__).parent / "landing_template.html"


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


def _clean_body(raw: str) -> str:
    """
    Normaliza el cuerpo que devuelve Claude:
    - Elimina vallas de código markdown (```html ... ```).
    - Si por error devuelve un documento completo, extrae solo el contenido del <body>.
    - Elimina cualquier <style>, <head>, <header> o <footer> que se haya colado
      (el shell estático ya los aporta).
    """
    text = raw.strip()

    # Quitar vallas ```html / ```
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()

    # Si devolvió un documento completo, quedarnos con el interior del <body>.
    body_match = re.search(r"<body[^>]*>(.*)</body>", text, re.DOTALL | re.IGNORECASE)
    if body_match:
        text = body_match.group(1).strip()

    # Eliminar bloques que el shell ya provee y que romperían el diseño.
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?(?:html|body)[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)

    return text.strip()


def build_output_3_html(body_html: str, titulo: str = "Landing — Innóvate 4.0") -> str:
    """Envuelve el cuerpo de la landing en la plantilla estática y devuelve el HTML completo."""
    body = _clean_body(body_html)
    html = _load_template()
    html = html.replace("{{LANDING_BODY}}", body)
    html = html.replace("{{TITULO}}", titulo)
    html = html.replace("{{LOGO_SRC}}", _load_logo_b64())
    return html
