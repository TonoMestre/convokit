"""
ConvoKit — Builder para la Salida 3 (Landing page HTML).

Flujo de generación:
1. Claude devuelve DOS partes separadas por marcadores:
     ===SEO_JSON===
     {"seo_title": ..., "meta_description": ..., "slug": ...}
     ===LANDING_HTML===
     <section class="hero">...   (solo el cuerpo, con clases CSS documentadas)
2. parse_landing_response(raw) separa los campos SEO del cuerpo HTML.
3. build_output_3_html(body, seo_title, meta_description) envuelve el cuerpo en la
   plantilla estática landing_template.html, inyectando título y meta description en
   el <head>. El slug NO se inserta en el HTML: es un campo independiente que el
   usuario copia manualmente a WordPress/Yoast.

El HTML resultante es completo y autónomo: una página válida por sí sola.
"""

import base64
import json
import pathlib
import re
import unicodedata

_TEMPLATE_PATH = pathlib.Path(__file__).parent / "landing_template.html"

_SEO_MARKER = "===SEO_JSON==="
_HTML_MARKER = "===LANDING_HTML==="

# Distribución de fondos por bloque (1..8) para cada variante.
# El contenido y el SEO son idénticos en las tres: solo cambia el fondo de cada bloque,
# para que dos convocatorias publicadas a la vez no se vean estructuralmente calcadas.
# Bloques: 1 hero · 2 qué consigue · 3 a quién · 4 qué financia · 5 importe · 6 cómo trabajamos · 7 CTA final · 8 Ruta i40
VALID_VARIANTS = {"A", "B"}
DEFAULT_VARIANT = "A"


def normalize_variant(variant: str | None) -> str:
    v = (variant or "").strip().upper()
    return v if v in VALID_VARIANTS else DEFAULT_VARIANT


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


def _esc_attr(text: str) -> str:
    """Escapa para usar dentro de un atributo HTML (content="...", etc.)."""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _esc_text(text: str) -> str:
    """Escapa para usar como texto (p. ej. dentro de <title>)."""
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slugify(text: str) -> str:
    """Convierte un texto en un slug url-safe (minúsculas, sin tildes, guiones)."""
    norm = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9]+", "-", norm)
    return norm.strip("-")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        t = "\n".join(lines[1:end]).strip()
    return t


def _clean_body(raw: str) -> str:
    """
    Normaliza el cuerpo HTML que devuelve Claude:
    - Elimina vallas de código markdown.
    - Si por error devuelve un documento completo, extrae solo el <body>.
    - Elimina <style>, <head>, <header>, <footer> que se hayan colado (el shell ya los aporta).
    """
    text = _strip_fences(raw)

    body_match = re.search(r"<body[^>]*>(.*)</body>", text, re.DOTALL | re.IGNORECASE)
    if body_match:
        text = body_match.group(1).strip()

    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?(?:html|body)[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)

    return text.strip()


def parse_landing_response(raw: str, fallback_name: str = "") -> tuple[dict, str]:
    """
    Separa la respuesta de Claude en (seo, body_html).

    seo = {"seo_title": str, "meta_description": str, "slug": str}

    Robusto ante:
    - Marcadores presentes (caso normal).
    - Marcadores ausentes: trata todo como cuerpo y deriva SEO best-effort del nombre.
    - JSON con vallas markdown.
    """
    seo: dict = {"seo_title": "", "meta_description": "", "slug": ""}

    if _HTML_MARKER in raw:
        seo_part, _, body_part = raw.partition(_HTML_MARKER)
        seo_part = seo_part.replace(_SEO_MARKER, "").strip()
        body = body_part
        try:
            parsed = json.loads(_strip_fences(seo_part))
            if isinstance(parsed, dict):
                seo.update({k: parsed.get(k, "") for k in seo})
        except Exception:
            pass
    else:
        # Sin marcadores: todo es cuerpo. Intentar extraer un JSON SEO suelto al principio.
        body = raw
        m = re.search(r"\{[^{}]*\"seo_title\".*?\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict):
                    seo.update({k: parsed.get(k, "") for k in seo})
                body = raw.replace(m.group(0), "")
            except Exception:
                pass

    # Rellenar huecos con valores derivados del nombre de la convocatoria.
    if not seo["seo_title"]:
        seo["seo_title"] = fallback_name.strip()
    if not seo["slug"]:
        seo["slug"] = slugify(seo["seo_title"] or fallback_name)
    if not seo["meta_description"]:
        seo["meta_description"] = seo["seo_title"]

    return seo, _clean_body(body)


def build_output_3_html(
    body_html: str,
    seo_title: str,
    meta_description: str,
    variant: str = DEFAULT_VARIANT,
) -> str:
    """
    Envuelve el cuerpo de la landing en la plantilla estática, aplica la variante de
    distribución (fondos por bloque) e inyecta el SEO en el <head>.
    El slug NO se usa aquí: no se inserta en el HTML.
    """
    variant = normalize_variant(variant)
    body = _clean_body(body_html)

    html = _load_template()
    html = html.replace("{{LANDING_BODY}}", body)
    html = html.replace("{{VARIANT_CLASS}}", f"variante-{variant.lower()}")
    html = html.replace("{{SEO_TITLE}}", _esc_text(seo_title) or "Innóvate 4.0")
    html = html.replace("{{META_DESCRIPTION}}", _esc_attr(meta_description))
    html = html.replace("{{LOGO_SRC}}", _load_logo_b64())
    return html
