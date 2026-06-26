"""
ConvoKit — extracción de texto de documentos.

Extrae el contenido textual de cada formato admitido usando librerías locales.
Ninguna llamada externa: cero tokens de Claude consumidos en esta fase.

Paso 3: extracción de PDF (PyMuPDF).
Paso 4: se añade DOCX (python-docx) y XLSX (openpyxl).
"""

import fitz  # PyMuPDF


# Etiquetas que se muestran como cabecera en el contexto compuesto.
LABEL_HEADERS = {
    "bases_reguladoras":   "BASES REGULADORAS",
    "convocatoria":        "CONVOCATORIA DEL EJERCICIO",
    "plantilla_memoria":   "PLANTILLA DE MEMORIA / SOLICITUD",
    "resolucion_anterior": "RESOLUCIÓN DE EJERCICIO ANTERIOR",
    "anexo":               "ANEXO O DOCUMENTO COMPLEMENTARIO",
}


def extract_text(content: bytes, filename: str) -> str:
    """
    Detecta el formato por extensión y delega en el extractor correspondiente.
    Lanza ValueError con mensaje en español si el formato no es compatible o
    si el PDF no tiene texto extraíble (escaneado).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf(content, filename)
    elif ext == "txt":
        return _extract_txt(content)
    else:
        # DOCX y XLSX se añaden en el Paso 4.
        raise ValueError(
            f"Formato no soportado: .{ext}. "
            "Sube el archivo en PDF, DOCX, XLSX o TXT."
        )


def build_context(documents: list[dict]) -> str:
    """
    Combina el texto extraído de todos los documentos en un único contexto
    compuesto, prefijando cada bloque con su etiqueta.

    Si el contexto total supera 150.000 palabras, trunca por orden de
    prioridad: bases_reguladoras → convocatoria → plantilla_memoria →
    resolucion_anterior → anexo.
    """
    PRIORITY = [
        "bases_reguladoras",
        "convocatoria",
        "plantilla_memoria",
        "resolucion_anterior",
        "anexo",
    ]
    MAX_WORDS = 150_000

    # Ordenar por prioridad para aplicar el límite correctamente.
    sorted_docs = sorted(
        documents,
        key=lambda d: PRIORITY.index(d["etiqueta"]) if d["etiqueta"] in PRIORITY else 99,
    )

    parts = []
    total_words = 0

    for doc in sorted_docs:
        header = LABEL_HEADERS.get(doc["etiqueta"], doc["etiqueta"].upper())
        block = f"=== {header} ===\n{doc['texto']}"
        words = len(block.split())

        if total_words + words > MAX_WORDS:
            # Incluir solo la parte que cabe.
            remaining = MAX_WORDS - total_words
            truncated = " ".join(block.split()[:remaining])
            parts.append(truncated + "\n[... documento truncado por límite de contexto ...]")
            break

        parts.append(block)
        total_words += words

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Extractores por formato
# ---------------------------------------------------------------------------

def _extract_pdf(content: bytes, filename: str) -> str:
    """
    Extrae texto de un PDF con PyMuPDF, página a página.
    Lanza ValueError si el PDF no tiene texto (escaneado).
    """
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:
        raise ValueError(f"No se pudo abrir el archivo '{filename}'. Comprueba que es un PDF válido.")

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise ValueError(
            "Este PDF parece estar escaneado y no contiene texto extraíble. "
            "Por favor, aporta la versión digital del documento."
        )

    return full_text


def _extract_txt(content: bytes) -> str:
    """
    Lee un fichero de texto plano en UTF-8 con fallback a latin-1.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")
