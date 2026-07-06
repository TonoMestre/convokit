"""
ConvoKit — Builder para la Salida 3 (Landing page HTML para WordPress).

Flujo de generación:
1. Claude devuelve DOS partes separadas por marcadores:
     ===SEO_JSON===
     {"seo_title": ..., "meta_description": ..., "slug": ..., "h1_recomendado": ...,
      "keywords_principales": [...], "faqs_sugeridas": [...]}
     ===LANDING_HTML===
     <section class="hero">...   (solo el cuerpo, con clases CSS documentadas)
2. parse_landing_response(raw) separa los campos SEO del cuerpo HTML.
3. build_output_3_html(body, slug, variant, cfg) envuelve el cuerpo en la plantilla
   estática landing_template.html: un bloque scoped bajo #innovate-ayuda-landing-{slug}
   (CSS, wrapper, header y footer incluidos), SIN doctype/html/head/body. Los campos
   SEO (título, meta description, H1, keywords, FAQs) NO se insertan en el HTML: se
   devuelven aparte para que el consultor los configure en Yoast/RankMath, ya que la
   landing se pega directamente en una página de WordPress que ya tiene su propio <head>.

Si `cfg` no es None y el cuerpo contiene el marcador `<!--EVALUADOR_EMBED-->` (lo decide
el propio prompt según el flag INCLUIR_EVALUADOR), se sustituye por el fragmento del
evaluador (mismo motor que la salida 6, ver output6_template.build_output_6_embed_fragment).
Si `cfg` es None o el marcador no aparece, la sustitución es un no-op.
"""

import base64
import json
import pathlib
import re
import unicodedata

import output6_template

_TEMPLATE_PATH = pathlib.Path(__file__).parent / "landing_template.html"

_SEO_MARKER = "===SEO_JSON==="
_HTML_MARKER = "===LANDING_HTML==="
_EVALUADOR_MARKER = "<!--EVALUADOR_EMBED-->"

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

    seo = {"seo_title", "meta_description", "slug", "h1_recomendado",
           "keywords_principales", "faqs_sugeridas"}

    Robusto ante:
    - Marcadores presentes (caso normal).
    - Marcadores ausentes: trata todo como cuerpo y deriva SEO best-effort del nombre.
    - JSON con vallas markdown.
    """
    seo: dict = {
        "seo_title": "", "meta_description": "", "slug": "",
        "h1_recomendado": "", "keywords_principales": [], "faqs_sugeridas": [],
    }

    if _HTML_MARKER in raw:
        seo_part, _, body_part = raw.partition(_HTML_MARKER)
        seo_part = seo_part.replace(_SEO_MARKER, "").strip()
        body = body_part
        try:
            parsed = json.loads(_strip_fences(seo_part))
            if isinstance(parsed, dict):
                seo.update({k: parsed.get(k, seo[k]) for k in seo})
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
    if not seo["h1_recomendado"]:
        seo["h1_recomendado"] = seo["seo_title"]
    if not isinstance(seo["keywords_principales"], list):
        seo["keywords_principales"] = []
    if not isinstance(seo["faqs_sugeridas"], list):
        seo["faqs_sugeridas"] = []

    return seo, _clean_body(body)


def build_output_3_html(
    body_html: str,
    slug: str,
    variant: str = DEFAULT_VARIANT,
    cfg: dict | None = None,
) -> str:
    """
    Envuelve el cuerpo de la landing en la plantilla estática: un bloque scoped bajo
    #innovate-ayuda-landing-{slug}, sin doctype/html/head/body, listo para pegar en el
    bloque "HTML personalizado" de WordPress. Aplica la variante de distribución
    (fondos por bloque). El SEO (título, meta description, H1, keywords, FAQs) no se
    inserta aquí: se sirve aparte para que el consultor lo configure en Yoast/RankMath.

    Si `cfg` se proporciona y el cuerpo contiene el marcador del evaluador embebido,
    lo sustituye por el fragmento del motor del evaluador (misma lógica que la
    salida 6). Si no hay marcador, o `cfg` es None, no hace nada.
    """
    variant = normalize_variant(variant)
    body = _clean_body(body_html)

    if cfg is not None and _EVALUADOR_MARKER in body:
        embed_fragment = output6_template.build_output_6_embed_fragment(cfg)
        body = body.replace(_EVALUADOR_MARKER, embed_fragment)

    wrapper_id = f"innovate-ayuda-landing-{slugify(slug) or 'convocatoria'}"

    html = _load_template()
    html = html.replace("{{LANDING_BODY}}", body)
    html = html.replace("{{WRAPPER_SELECTOR}}", f"#{wrapper_id}")
    html = html.replace("{{WRAPPER_ID}}", wrapper_id)
    html = html.replace("{{VARIANT_CLASS}}", f"variante-{variant.lower()}")
    html = html.replace("{{LOGO_SRC}}", _load_logo_b64())
    return html
