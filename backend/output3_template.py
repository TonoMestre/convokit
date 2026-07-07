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
   full-bleed (rompe la columna de contenido del tema de WordPress con width:100vw),
   SIN doctype/html/head/body y SIN header/footer propios (la web contenedora ya
   aporta menú y pie; duplicarlos pisaba la cabecera real de innovate40.es). Los campos
   SEO (título, meta description, H1, keywords, FAQs) NO se insertan en el HTML: se
   devuelven aparte para que el consultor los configure en Yoast/RankMath, ya que la
   landing se pega directamente en una página de WordPress que ya tiene su propio <head>.

Si `cfg` no es None y el cuerpo contiene el marcador `<!--EVALUADOR_EMBED-->` (lo decide
el propio prompt según el flag INCLUIR_EVALUADOR), se sustituye por el fragmento del
evaluador (mismo motor que la salida 6, ver output6_template.build_output_6_embed_fragment).
Si `cfg` es None o el marcador no aparece, la sustitución es un no-op.
"""

import html as html_lib
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


def slugify(text: str) -> str:
    """Convierte un texto en un slug url-safe (minúsculas, sin tildes, guiones)."""
    norm = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9]+", "-", norm)
    return norm.strip("-")


_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# Topes de Yoast: el prompt ya los exige, esto es la red de seguridad determinista.
_SEO_TITLE_MAX = 60
_META_DESCRIPTION_MAX = 142


def _strip_years(text: str) -> str:
    """Elimina años sueltos (1900-2099): las landing posicionan por el nombre de la
    ayuda, no por la edición, y la URL/título deben sobrevivir de un año al siguiente."""
    cleaned = _YEAR_RE.sub("", text or "")
    cleaned = re.sub(r"\s+([:;,.])", r"\1", cleaned)  # sin espacio huérfano ante puntuación
    return re.sub(r"\s{2,}", " ", cleaned).strip(" -:,")


def _truncate_at_word(text: str, max_len: int) -> str:
    """Recorta a max_len sin partir palabras y sin dejar puntuación colgando."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len + 1]
    cut = cut[:cut.rfind(" ")] if " " in cut else cut[:max_len]
    return cut.rstrip(" ,;:.-")


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
        "frase_clave": "", "seo_title": "", "meta_description": "", "slug": "",
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
    if not seo["frase_clave"]:
        base = _strip_years(fallback_name) or fallback_name
        seo["frase_clave"] = f"ayudas {base}".strip().lower()
    if not seo["slug"]:
        seo["slug"] = slugify(seo["frase_clave"] or seo["seo_title"] or fallback_name)
    if not seo["meta_description"]:
        seo["meta_description"] = seo["seo_title"]
    if not seo["h1_recomendado"]:
        seo["h1_recomendado"] = seo["seo_title"]
    if not isinstance(seo["keywords_principales"], list):
        seo["keywords_principales"] = []
    if not isinstance(seo["faqs_sugeridas"], list):
        seo["faqs_sugeridas"] = []

    # Red de seguridad determinista sobre las reglas del prompt: sin año en
    # frase_clave/título/slug (posicionan por nombre, no por edición) y topes
    # de longitud de Yoast (60 título / 142 meta description). La meta NO se
    # limpia de años en código: puede contener referencias factuales legítimas
    # ("la dana de 2024") que la regex rompería; ahí manda solo el prompt.
    seo["frase_clave"] = _strip_years(seo["frase_clave"]).lower()
    seo["seo_title"] = _truncate_at_word(_strip_years(seo["seo_title"]), _SEO_TITLE_MAX)
    seo["meta_description"] = _truncate_at_word(seo["meta_description"].strip(), _META_DESCRIPTION_MAX)
    seo["slug"] = slugify(_strip_years(seo["slug"].replace("-", " ")))

    return seo, _clean_body(body)


def _build_faqs_fragment(faqs: list) -> str:
    """
    Sección visible de FAQs (H2 + un H3 por pregunta) + marcado Schema FAQPage
    (JSON-LD). Se renderiza aquí, no en el prompt, para garantizar que el schema
    coincide EXACTAMENTE con el contenido visible (requisito de Google para los
    rich results). Devuelve cadena vacía si no hay FAQs válidas.
    """
    valid = [
        f for f in (faqs or [])
        if isinstance(f, dict) and (f.get("pregunta") or "").strip() and (f.get("respuesta") or "").strip()
    ]
    if not valid:
        return ""

    items_html = "".join(
        '<div class="faq-item"><h3>{q}</h3><p>{r}</p></div>'.format(
            q=html_lib.escape(f["pregunta"].strip()),
            r=html_lib.escape(f["respuesta"].strip()),
        )
        for f in valid
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["pregunta"].strip(),
                "acceptedAnswer": {"@type": "Answer", "text": f["respuesta"].strip()},
            }
            for f in valid
        ],
    }
    # </ escapado para no cerrar el <script> prematuramente
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")

    return (
        '<section class="bloque faqs"><div class="wrap">'
        '<h2 class="bloque-titulo">Preguntas frecuentes</h2>'
        f"{items_html}"
        "</div></section>\n"
        f'<script type="application/ld+json">{schema_json}</script>\n'
    )


_CONTACT_SECTION_RE = re.compile(r'<section[^>]*id="contacto"', re.IGNORECASE)


def build_output_3_html(
    body_html: str,
    slug: str,
    variant: str = DEFAULT_VARIANT,
    cfg: dict | None = None,
    faqs: list | None = None,
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

    # Sección de FAQs + Schema FAQPage: se inserta antes del formulario de
    # contacto (y antes del evaluador embebido si lo hay), tras las secciones
    # 1-8 — no altera los nth-child(3..5) de las variantes de color.
    faqs_fragment = _build_faqs_fragment(faqs)
    if faqs_fragment:
        m = _CONTACT_SECTION_RE.search(body)
        insert_at = m.start() if m else len(body)
        if _EVALUADOR_MARKER in body:
            insert_at = min(insert_at, body.index(_EVALUADOR_MARKER))
            # el marcador vive dentro de su <section>; retroceder hasta abrirla
            section_start = body.rfind("<section", 0, insert_at)
            if section_start != -1:
                insert_at = section_start
        body = body[:insert_at] + faqs_fragment + body[insert_at:]

    if cfg is not None and _EVALUADOR_MARKER in body:
        embed_fragment = output6_template.build_output_6_embed_fragment(cfg)
        body = body.replace(_EVALUADOR_MARKER, embed_fragment)

    wrapper_id = f"innovate-ayuda-landing-{slugify(slug) or 'convocatoria'}"

    html = _load_template()
    html = html.replace("{{LANDING_BODY}}", body)
    html = html.replace("{{WRAPPER_SELECTOR}}", f"#{wrapper_id}")
    html = html.replace("{{WRAPPER_ID}}", wrapper_id)
    html = html.replace("{{VARIANT_CLASS}}", f"variante-{variant.lower()}")
    return html
