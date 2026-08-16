"""
ConvoKit — modo de generación por i40 Knowledge Pack.

Fuente canónica de conocimiento normativo alternativa a los documentos
originales de la convocatoria (bases, convocatoria del ejercicio, guía).
En este modo ConvoKit sigue leyendo directamente la plantilla oficial de
memoria y los entregables a cumplimentar (Excel de costes, anexos) para
obtener ESTRUCTURA, pero el CONOCIMIENTO NORMATIVO (puntos, subcriterios,
umbrales, exclusiones, límites, reglas de coste, documentación exigida,
reglas procedimentales) procede exclusivamente del Knowledge Pack.

Regla crítica (no reinterpretación normativa): ninguna función de este
módulo lee texto de la plantilla o del Excel para inferir hechos
normativos. Si el Knowledge Pack no cubre lo que un apartado necesita,
se registra un `knowledge_gap` — nunca se rellena desde el entregable.

Dos ejes de estado, independientes:
  - `evidence_status`: vocabulario de i40 Analiza (evidence-status.schema.json).
    Describe la confianza evidencial del hecho. `not_located` significa
    "desconocido", nunca "no existe"; `conflict` significa que hay
    versiones contradictorias sin resolver.
  - `review_state`: si un humano ya validó el hecho (`human_validated`) o
    todavía no (`unvalidated`). Un hecho `accredited` pero `unvalidated`
    puede usarse, pero queda marcado internamente como no validado.

Nada de este módulo cambia el contrato de salida v2.5 (docs/contrato-convokit.md):
el objeto que produce `build_v25_root_from_kp` es exactamente el mismo tipo de
objeto que produce `_generate_output_4` a partir de documentos, y pasa por el
mismo `exporters.export_output_4` sin modificarlo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Vocabularios
# ---------------------------------------------------------------------------

# Vocabulario real de i40 Analiza (apps/web/src/lib/contracts/schemas/evidence-status.schema.json).
# Se reutiliza tal cual: no se inventa un vocabulario paralelo de confianza evidencial.
EVIDENCE_STATUS_VALUES = {
    "pending", "accredited", "inferred", "not_provided", "not_located",
    "not_published", "not_evaluated", "not_evaluable", "not_applicable",
    "conflict", "operational", "provider_output_failed",
}

# Eje ortogonal, propio de este modo: ¿lo validó un humano?
REVIEW_STATES = {"human_validated", "unvalidated"}

# Tipos de entidad normativa que puede contener un Knowledge Pack. Cierran el
# vocabulario de "hecho normativo" que puede alimentar un apartado: cualquier
# cosa que no encaje en uno de estos tipos no se trata como norma.
ENTITY_TYPES = {
    "criterion",       # criterio de baremo con puntuación (p.ej. "II.B" -> 4 pt)
    "subcriterion",    # sub-criterio dentro de un criterio (p.ej. "ratio de rentabilidad" -> 2 pt)
    "threshold",       # umbral mínimo / de corte
    "exclusion",       # criterio excluyente / requisito de admisión
    "requirement",     # requisito general (elegibilidad, plazo, forma)
    "limit",           # límite cuantitativo (importe, %, fecha)
    "cost_rule",       # regla de gasto subvencionable / categoría de coste
    "documentation",   # documento exigido
    "procedural_rule", # regla de procedimiento (plazos, subsanación, notificación)
}

EntityType = Literal[
    "criterion", "subcriterion", "threshold", "exclusion", "requirement",
    "limit", "cost_rule", "documentation", "procedural_rule",
]


class KnowledgePackError(ValueError):
    """JSON de entrada que no es un Knowledge Pack válido o utilizable."""


# ---------------------------------------------------------------------------
# Modelo interno
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceRef:
    """Referencia a evidencia documental de i40 Analiza (evidence-ref.schema.json,
    campos relevantes para auditoría de procedencia; no se reenvía a MemorAI)."""
    document_id: str
    quote: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class NormativeEntity:
    """Un hecho normativo individual del Knowledge Pack."""
    entity_id: str
    entity_type: EntityType
    section_ref: str          # descripción libre de a qué apartado/bloque de la convocatoria se refiere
    label: str                # qué es, en lenguaje natural (p.ej. "Ratio de rentabilidad y método")
    value: object              # el valor estructurado: número de puntos, texto de la regla, etc.
    evidence_status: str
    review_state: str
    confidence: float | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()
    conflict_group_id: str | None = None  # si evidence_status == "conflict", agrupa las versiones en conflicto
    conflicting_values: tuple[object, ...] = ()  # las versiones contradictorias, preservadas sin elegir una

    def is_missing(self) -> bool:
        return self.evidence_status in ("not_provided", "not_located") or self.value is None

    def is_conflict(self) -> bool:
        return self.evidence_status == "conflict"

    def is_canonical(self) -> bool:
        """Puede usarse como verdad normativa sin más matices."""
        return self.review_state == "human_validated" and not self.is_conflict() and not self.is_missing()

    def is_usable_but_unvalidated(self) -> bool:
        return (
            self.evidence_status == "accredited"
            and self.review_state == "unvalidated"
            and not self.is_conflict()
        )


@dataclass
class KnowledgePack:
    pack_id: str
    convocatoria_ref: str
    entities: list[NormativeEntity]
    schema_version: str = "0.1-synthetic"
    # Metadatos de identificación de la convocatoria (nombre oficial, año,
    # organismo, tipo de ayuda), si el pack los trae. No son "criterios" pero
    # sí conocimiento que en modo documental extraía Claude leyendo la
    # convocatoria; en modo Knowledge Pack, si el pack no los trae, quedan
    # como valor de escape (nunca se infieren de la plantilla).
    convocatoria_metadata: dict = field(default_factory=dict)

    def by_type(self, entity_type: EntityType) -> list[NormativeEntity]:
        return [e for e in self.entities if e.entity_type == entity_type]


# ---------------------------------------------------------------------------
# Parseo estricto del JSON de entrada
# ---------------------------------------------------------------------------

def _parse_evidence_ref(raw: dict) -> EvidenceRef:
    if not isinstance(raw, dict) or "document_id" not in raw or "quote" not in raw:
        raise KnowledgePackError("evidence_ref inválida: requiere document_id y quote.")
    return EvidenceRef(
        document_id=str(raw["document_id"]),
        quote=str(raw["quote"]),
        section=raw.get("section"),
        page_start=raw.get("page_start"),
        page_end=raw.get("page_end"),
    )


def _parse_entity(raw: dict, index: int) -> NormativeEntity:
    if not isinstance(raw, dict):
        raise KnowledgePackError(f"entities[{index}] no es un objeto.")

    entity_type = raw.get("entity_type")
    if entity_type not in ENTITY_TYPES:
        raise KnowledgePackError(
            f"entities[{index}]: entity_type '{entity_type}' fuera del vocabulario {sorted(ENTITY_TYPES)}."
        )

    evidence_status = raw.get("evidence_status")
    if evidence_status not in EVIDENCE_STATUS_VALUES:
        raise KnowledgePackError(
            f"entities[{index}]: evidence_status '{evidence_status}' fuera del vocabulario "
            f"{sorted(EVIDENCE_STATUS_VALUES)}."
        )

    review_state = raw.get("review_state", "unvalidated")
    if review_state not in REVIEW_STATES:
        raise KnowledgePackError(f"entities[{index}]: review_state '{review_state}' inválido.")

    entity_id = raw.get("entity_id")
    if not entity_id or not isinstance(entity_id, str):
        raise KnowledgePackError(f"entities[{index}]: falta entity_id estable.")

    section_ref = raw.get("section_ref") or ""
    label = raw.get("label") or ""
    if not label:
        raise KnowledgePackError(f"entities[{index}] ({entity_id}): falta label.")

    evidence_refs = tuple(_parse_evidence_ref(r) for r in (raw.get("evidence_refs") or []))

    conflict_group_id = raw.get("conflict_group_id")
    conflicting_values = tuple(raw.get("conflicting_values") or ())
    if evidence_status == "conflict" and not conflicting_values:
        raise KnowledgePackError(
            f"entities[{index}] ({entity_id}): evidence_status='conflict' sin conflicting_values; "
            "un conflicto debe preservar las versiones contradictorias, no perderlas."
        )

    return NormativeEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        section_ref=section_ref,
        label=label,
        value=raw.get("value"),
        evidence_status=evidence_status,
        review_state=review_state,
        confidence=raw.get("confidence"),
        evidence_refs=evidence_refs,
        conflict_group_id=conflict_group_id,
        conflicting_values=conflicting_values,
    )


def parse_knowledge_pack(raw: dict) -> KnowledgePack:
    """
    Parsea y valida el JSON del i40 Knowledge Pack. Preserva internamente todo:
    valor, tipo, evidence_refs, evidence_status, review_state, scope (section_ref),
    confidence y conflictos. No descarta nada silenciosamente: cualquier entidad
    mal formada detiene el parseo con un error explícito (misma filosofía que
    "fallar en voz alta" del contrato v2.5, no entregar un pack a medias sin avisar).
    """
    if not isinstance(raw, dict):
        raise KnowledgePackError("El Knowledge Pack debe ser un objeto JSON, no un array.")
    if not raw.get("pack_id"):
        raise KnowledgePackError("Falta 'pack_id'.")
    if not raw.get("convocatoria_ref"):
        raise KnowledgePackError("Falta 'convocatoria_ref'.")

    entities_raw = raw.get("entities")
    if not isinstance(entities_raw, list) or not entities_raw:
        raise KnowledgePackError("'entities' debe ser un array no vacío.")

    entities = [_parse_entity(e, i) for i, e in enumerate(entities_raw)]

    ids = [e.entity_id for e in entities]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise KnowledgePackError(f"entity_id repetidos: {sorted(dupes)}.")

    return KnowledgePack(
        pack_id=str(raw["pack_id"]),
        convocatoria_ref=str(raw["convocatoria_ref"]),
        entities=entities,
        schema_version=str(raw.get("schema_version") or "0.1-synthetic"),
        convocatoria_metadata=dict(raw.get("convocatoria_metadata") or {}),
    )


# ---------------------------------------------------------------------------
# Matching plantilla <-> Knowledge Pack (determinista, sin llamada a Claude)
# ---------------------------------------------------------------------------
#
# Se elige un matcher determinista, no un modelo, a propósito: el punto 6 del
# encargo exige poder responder "por qué" se asoció cada entidad a un apartado
# sin volver a leer nada, y "no inventes un identificador cuando no exista".
# Un matcher determinista es auditable y testeable sin red; el coste es que
# depende de que section_ref del Knowledge Pack use vocabulario reconocible
# (nombre/código del apartado). Cuando la señal es débil, se marca como
# revisión requerida en vez de asumir una coincidencia.

_STOPWORDS_ES = {
    "de", "la", "el", "los", "las", "y", "o", "en", "del", "al", "a", "que",
    "para", "por", "un", "una", "su", "sus", "con", "e", "u",
}

_STRONG_MATCH_THRESHOLD = 0.5
_WEAK_MATCH_THRESHOLD = 0.2


def _normalize_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    only_alnum = re.sub(r"[^a-z0-9\s.]", " ", without_accents)
    return {t for t in only_alnum.split() if t not in _STOPWORDS_ES and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


def label_similarity(text_a: str, text_b: str) -> float:
    """Solapamiento de tokens (0-1) entre dos textos libres. Función pública
    de conveniencia para quien necesite reutilizar el mismo criterio de
    similitud que usa el matcher de apartados (p.ej. para emparejar un input
    concreto con la entidad normativa que lo originó, ver stable_input_id)."""
    return _jaccard(_normalize_tokens(text_a), _normalize_tokens(text_b))


@dataclass
class MatchedEntity:
    entity: NormativeEntity
    confidence: float
    match_basis: str  # qué señal produjo el match, para auditoría


@dataclass
class SectionMatch:
    """Resultado de asociar un apartado del entregable (codigo, nombre) con el
    conocimiento del Knowledge Pack relevante para él."""
    codigo: str
    nombre: str
    matched: list[MatchedEntity]
    match_state: Literal["strong", "weak", "none"]

    def entities(self) -> list[NormativeEntity]:
        return [m.entity for m in self.matched]

    def by_type(self, entity_type: EntityType) -> list[NormativeEntity]:
        return [m.entity for m in self.matched if m.entity.entity_type == entity_type]


# ---------------------------------------------------------------------------
# Endurecimiento 2 — expectativa de puntuación en tres estados
# ---------------------------------------------------------------------------
#
# Saber si un apartado puntúa es en sí mismo conocimiento normativo: no puede
# derivarse de la plantilla ("(máx. X puntos)" no cuenta) ni asumirse por
# defecto. Se deriva EXCLUSIVAMENTE de las entidades del Knowledge Pack ya
# emparejadas por match_section_to_knowledge — nunca del entregable.
#
# Mecanismo: el vocabulario real de i40 Analiza ya distingue "not_applicable"
# ("el criterio no procede en el caso concreto", contracts/evidence-status
# .schema.json + docs/14_NOMENCLATURA_GLOSARIO.md) de "not_located"/
# "not_provided" (desconocido). Una entidad 'criterion' con evidence_status
# 'not_applicable' es el pack afirmando explícitamente que el apartado no
# puntúa; eso basta para 'not_scored' sin inventar un mecanismo nuevo.

ScoringExpectation = Literal["scored", "not_scored", "unknown"]


def compute_scoring_expectation(section_match: SectionMatch) -> ScoringExpectation:
    """
    Deriva si el apartado puntúa exclusivamente de las entidades 'criterion'
    emparejadas del Knowledge Pack. Nunca lee la plantilla, el Excel ni ningún
    otro entregable.

    - 'scored': hay al menos una entidad 'criterion' usable (canónica o
      accreditada-sin-validar) con un valor real distinto de 'no aplica'.
    - 'not_scored': hay al menos una entidad 'criterion' usable cuyo
      evidence_status es 'not_applicable' — el pack afirma expresamente que
      este apartado no puntúa.
    - 'unknown' en cualquier otro caso: sin entidad 'criterion' emparejada,
      solo entidades en conflicto, o solo entidades missing (not_located/
      not_provided). Un 'criterion' en conflicto NUNCA convierte el apartado
      en 'scored' de forma firme, aunque una de sus versiones contradictorias
      tenga puntos.
    """
    criteria = section_match.by_type("criterion")

    not_scored_entities = [e for e in criteria if e.evidence_status == "not_applicable"]
    if not_scored_entities:
        return "not_scored"

    scored_entities = [
        e for e in criteria
        if (e.is_canonical() or e.is_usable_but_unvalidated()) and e.value is not None
    ]
    if scored_entities:
        return "scored"

    return "unknown"


def match_section_to_knowledge(codigo: str, nombre: str, pack: KnowledgePack) -> SectionMatch:
    """
    Empareja un apartado (codigo+nombre, obtenidos de la plantilla) con las
    entidades normativas del pack cuyo `section_ref` es semánticamente afín.
    No usa igualdad literal: compara solapamiento de tokens entre `nombre` y
    `section_ref`, y una coincidencia exacta o de prefijo del `codigo` dentro
    de `section_ref` sube la confianza.
    """
    codigo_norm = (codigo or "").strip().lower()
    nombre_tokens = _normalize_tokens(nombre)

    matched: list[MatchedEntity] = []
    for entity in pack.entities:
        ref_tokens = _normalize_tokens(entity.section_ref)
        score = _jaccard(nombre_tokens, ref_tokens)

        ref_lower = (entity.section_ref or "").lower()
        basis = "token_overlap"
        if codigo_norm and re.search(rf"(^|[^a-z0-9]){re.escape(codigo_norm)}([^a-z0-9]|$)", ref_lower):
            score = max(score, 0.75)
            basis = "codigo_exacto"

        if score >= _WEAK_MATCH_THRESHOLD:
            matched.append(MatchedEntity(entity=entity, confidence=round(score, 3), match_basis=basis))

    matched.sort(key=lambda m: m.confidence, reverse=True)

    if any(m.confidence >= _STRONG_MATCH_THRESHOLD for m in matched):
        state = "strong"
    elif matched:
        state = "weak"
    else:
        state = "none"

    return SectionMatch(codigo=codigo, nombre=nombre, matched=matched, match_state=state)


# ---------------------------------------------------------------------------
# Gaps — calculados ANTES de llamar a Claude, nunca inferidos por el modelo
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeGap:
    codigo: str
    kind: Literal[
        "no_match", "weak_match", "missing_entity_type", "conflict_unresolved", "entity_unknown",
        "scoring_status_unknown",
    ]
    detail: str
    entity_type: str | None = None
    entity_id: str | None = None


# Tipos de entidad que "todo apartado con criterio de valoración" debería tener
# cubiertos para no dejar al prompt sin la puntuación real. No es exhaustivo
# de todo lo que un apartado podría necesitar (eso lo decide cada caso); es el
# mínimo para poder afirmar "el baremo asigna X puntos a este apartado" sin
# acudir a la plantilla como fuente normativa.
_EXPECTED_FOR_SCORED_SECTION: tuple[EntityType, ...] = ("criterion",)


def compute_knowledge_gaps(
    section_match: SectionMatch, scoring_expectation: ScoringExpectation
) -> list[KnowledgeGap]:
    """
    `scoring_expectation` (endurecimiento 2) sustituye al antiguo booleano
    `expects_scoring`. Se calcula con `compute_scoring_expectation` — siempre
    a partir del Knowledge Pack, nunca de la plantilla — y cambia el
    tratamiento del hueco de puntuación:
      - 'scored': se exige una entidad 'criterion' utilizable; si falta, gap
        'missing_entity_type' (comportamiento idéntico al `expects_scoring=True`
        anterior).
      - 'not_scored': no se exige ningún 'criterion' (el pack ya afirma que
        este apartado no puntúa); no se genera 'missing_entity_type' por su
        ausencia.
      - 'unknown': tampoco se exige 'criterion' — asumirlo sería la misma
        inferencia no respaldada que este endurecimiento evita — y en su
        lugar se registra un gap explícito 'scoring_status_unknown'.
    En los tres casos, los gaps por entidad individual (conflicto, missing)
    se calculan igual, sin relación con `scoring_expectation`.
    """
    gaps: list[KnowledgeGap] = []

    if section_match.match_state == "none":
        gaps.append(KnowledgeGap(
            codigo=section_match.codigo, kind="no_match",
            detail=(
                f"Ninguna entidad del Knowledge Pack referencia el apartado {section_match.codigo} "
                f"({section_match.nombre}). No hay conocimiento normativo disponible para este apartado."
            ),
        ))
        return gaps

    if section_match.match_state == "weak":
        gaps.append(KnowledgeGap(
            codigo=section_match.codigo, kind="weak_match",
            detail=(
                f"El emparejamiento con el Knowledge Pack es débil (confianza < {_STRONG_MATCH_THRESHOLD}) "
                "para este apartado; requiere revisión antes de tratarse como asociación segura."
            ),
        ))

    if scoring_expectation == "scored":
        for entity_type in _EXPECTED_FOR_SCORED_SECTION:
            candidates = section_match.by_type(entity_type)
            usable = [e for e in candidates if e.is_canonical() or e.is_usable_but_unvalidated()]
            if not usable:
                gaps.append(KnowledgeGap(
                    codigo=section_match.codigo, kind="missing_entity_type",
                    entity_type=entity_type,
                    detail=(
                        f"No hay ninguna entidad de tipo '{entity_type}' utilizable en el Knowledge Pack "
                        f"para {section_match.codigo}. La plantilla podría mencionar una puntuación, pero "
                        "no se toma de ahí: se registra como hueco de conocimiento."
                    ),
                ))
    elif scoring_expectation == "unknown":
        gaps.append(KnowledgeGap(
            codigo=section_match.codigo, kind="scoring_status_unknown",
            detail=(
                f"El Knowledge Pack no permite determinar si {section_match.codigo} puntúa: no hay "
                "ninguna entidad 'criterion' utilizable ni ninguna marcada 'not_applicable'. No se "
                "asume ni 'scored' ni 'not_scored', y no se infiere de la plantilla ni del Excel."
            ),
        ))
    # scoring_expectation == "not_scored": el pack ya afirma que este apartado
    # no puntúa (entidad 'criterion' con evidence_status 'not_applicable');
    # no se exige ni se echa en falta ninguna puntuación.

    for entity in section_match.entities():
        if entity.is_conflict():
            gaps.append(KnowledgeGap(
                codigo=section_match.codigo, kind="conflict_unresolved",
                entity_type=entity.entity_type, entity_id=entity.entity_id,
                detail=(
                    f"Entidad '{entity.entity_id}' ({entity.label}) en conflicto: "
                    f"{len(entity.conflicting_values)} versiones sin resolver. No se eleva a hecho categórico."
                ),
            ))
        elif entity.is_missing():
            # Entidad individual conocida-como-desconocida (not_located/not_provided):
            # 'not_located' = desconocido, nunca 'no existe' (regla 5). Se registra su
            # propio gap nombrado, no solo la ausencia agregada por tipo, para poder
            # responder qué pieza normativa concreta falta (punto 9 del encargo).
            gaps.append(KnowledgeGap(
                codigo=section_match.codigo, kind="entity_unknown",
                entity_type=entity.entity_type, entity_id=entity.entity_id,
                detail=(
                    f"'{entity.label}' referenciado para {section_match.codigo} pero su valor es "
                    f"{entity.evidence_status} ({'desconocido, no ausente' if entity.evidence_status == 'not_located' else 'no aportado'}); "
                    "no se usa como hecho ni se infiere del entregable."
                ),
            ))

    return gaps


# ---------------------------------------------------------------------------
# Formateo determinista del conocimiento usable en texto para el prompt
# ---------------------------------------------------------------------------

def usable_entities(section_match: SectionMatch) -> list[NormativeEntity]:
    """Entidades que SÍ pueden emplearse para redactar: canónicas o accredited-sin-validar.
    Las `conflict`, `not_located`/`not_provided` (missing) y `pending`/`inferred` sin
    validación NO entran aquí — quedan como gap o como nota de cautela, nunca como hecho."""
    return [e for e in section_match.entities() if e.is_canonical() or e.is_usable_but_unvalidated()]


def format_normative_context(section_match: SectionMatch) -> str:
    """
    Construye el bloque de contexto normativo que se envía al modelo, EXCLUSIVAMENTE
    a partir de entidades usables del Knowledge Pack. Marca explícitamente las que
    están accredited-pero-sin-validar, para que el prompt las trate con la cautela
    correspondiente (regla del punto 5: 'accredited pero pendiente de revisión humana
    puede utilizarse, pero debe quedar marcado').
    """
    usable = usable_entities(section_match)
    if not usable:
        return ""

    lines = []
    for entity in usable:
        tag = "" if entity.review_state == "human_validated" else " [PENDIENTE DE VALIDACIÓN HUMANA]"
        lines.append(f"- ({entity.entity_type}) {entity.label}: {entity.value}{tag}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endurecimiento 1 — aislamiento determinista de DELIVERABLE_CONTEXT
# ---------------------------------------------------------------------------
#
# SECTION_PROMPT_SYSTEM_KP ya prohibía por instrucción usar una cifra de
# DELIVERABLE_CONTEXT como normativa. En la ejecución real de INPYME 2026 esa
# instrucción se cumplió en espíritu (nunca se presentó como hecho firme) pero
# no al pie de la letra: el modelo llegó a mencionar "hasta 1 punto" del
# pay-back con una salvedad, porque la cifra seguía siendo visible en el
# texto. Este módulo elimina esa posibilidad en código, antes de que el texto
# llegue al modelo: si el valor no está en el Knowledge Pack, no hay ninguna
# cifra que mencionar, con o sin salvedad.
#
# Alcance deliberadamente estrecho: solo enmascara expresiones cuantitativas
# con un calificador de magnitud normativa inequívoco pegado (máximo/mínimo/
# hasta/tope/límite/umbral) seguido de la unidad típica de un baremo o límite
# (puntos, %, €, días/meses/años). Un código de apartado ("II.B"), un nombre
# de sección, o un número estructural suelto ("3 columnas", "Anexo II") no
# lleva ese calificador pegado al número y por tanto nunca coincide.

NORMATIVE_VALUE_OMITTED_PLACEHOLDER = "[VALOR NORMATIVO OMITIDO — consultar NORMATIVE_CONTEXT]"

# Calificadores de magnitud normativa reconocidos: los explícitos (máximo/
# mínimo/hasta/tope/límite/umbral) más la formulación real que usa la
# convocatoria INPYME 2026 para el límite de ingeniería industrial ("no podrá
# superar el 15%... ni el importe de 20.000 €") — verificada en el documento
# real, no una suposición.
_MAGNITUDE_QUALIFIER = (
    r"(?:m[aá]x(?:imo|\.)?|m[ií]n(?:imo|\.)?|hasta|tope|l[ií]mite"
    r"|umbral\s+m[ií]nimo|umbral\s+m[aá]ximo"
    r"|no\s+podr[aá]\s+super(?:ar|ior)|no\s+puede\s+super(?:ar|ior)"
    r"|no\s+podr[aá]\s+exceder|no\s+superior\s+a)"
)
_OPTIONAL_ARTICLE = r"(?:el\s+|la\s+|los\s+|las\s+)?"

_SANITIZE_RULES: tuple[tuple[str, re.Pattern], ...] = (
    (
        "puntuacion",
        re.compile(
            rf"\(?{_MAGNITUDE_QUALIFIER}\s*\.?\s*{_OPTIONAL_ARTICLE}\d+([.,]\d+)?\s*(?:puntos?|pts?\.?)\)?",
            re.IGNORECASE,
        ),
    ),
    (
        "porcentaje",
        re.compile(
            rf"\(?{_MAGNITUDE_QUALIFIER}\s*\.?\s*{_OPTIONAL_ARTICLE}(?:del?\s+)?\d+([.,]\d+)?\s*%\)?",
            re.IGNORECASE,
        ),
    ),
    (
        "importe",
        re.compile(
            rf"\(?{_MAGNITUDE_QUALIFIER}\s*\.?\s*{_OPTIONAL_ARTICLE}(?:de\s+)?\d{{1,3}}(?:[.,]\d{{3}})*([.,]\d+)?\s*(?:€|eur(?:os)?\.?)\)?",
            re.IGNORECASE,
        ),
    ),
    (
        "plazo",
        re.compile(
            rf"\(?(?:plazo\s+)?{_MAGNITUDE_QUALIFIER}\s*\.?\s*{_OPTIONAL_ARTICLE}(?:de\s+)?\d+\s*(?:d[ií]as|meses|a[nñ]os)\)?",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class SanitizationHit:
    """Auditoría de una redacción concreta: qué regla disparó y qué texto se
    ocultó. Interna, nunca se envía a MemorAI ni forma parte del contrato v2.5."""
    rule: str
    original: str


def sanitize_deliverable_context(text: str) -> tuple[str, list[SanitizationHit]]:
    """
    Sanitiza DETERMINÍSTICAMENTE (sin IA) la representación de DELIVERABLE_CONTEXT
    que se envía al modelo en modo Knowledge Pack: sustituye cualquier expresión
    cuantitativa asociada de forma inequívoca a baremación o requisito normativo
    (puntuaciones, umbrales de puntuación, porcentajes/intensidades, importes o
    plazos normativos) por `NORMATIVE_VALUE_OMITTED_PLACEHOLDER`.

    NO toca códigos de apartado, nombres de sección, ni números estructurales
    (columnas de tabla, referencias a anexos): esos no llevan pegado ningún
    calificador de magnitud normativa (máximo/mínimo/hasta/tope/límite/umbral),
    que es la única señal que dispara una sustitución.

    Uso exclusivo del modo Knowledge Pack: `_slice_context_for_section` (usado
    también por el modo documental tradicional) no se modifica; esta función se
    aplica SOLO al resultado de esa función, y solo en `_generate_output_4_kp`.

    Devuelve (texto_sanitizado, hits) — `hits` es la auditoría interna (qué
    texto original se ocultó y con qué regla) para poder responder "por qué
    ConvoKit escribió esta instrucción" sin releer los documentos originales.
    El documento/contexto original nunca se modifica ni se descarta: esta
    función no toca `deliverable_documents_json`, solo la copia de texto que
    se ensambla para esta llamada concreta al modelo.
    """
    sanitized = text or ""
    hits: list[SanitizationHit] = []

    for rule_name, pattern in _SANITIZE_RULES:
        def _replace(match: re.Match, _rule=rule_name) -> str:
            hits.append(SanitizationHit(rule=_rule, original=match.group(0)))
            return NORMATIVE_VALUE_OMITTED_PLACEHOLDER

        sanitized = pattern.sub(_replace, sanitized)

    return sanitized, hits


# ---------------------------------------------------------------------------
# Extracción determinista de la "ficha" (parametros/tres_ofertas/documentos/
# datos_aplicativo) a partir del Knowledge Pack — sin llamada a Claude.
# ---------------------------------------------------------------------------
#
# Sustituye a OUTPUT_4_FICHA_EXTRACTOR (que en modo documental relee la
# convocatoria completa con Claude). En modo Knowledge Pack no se vuelve a
# pedir a Claude que descubra estas reglas leyendo bases/guía: se derivan
# deterministamente de las entidades ya extraídas y validadas por i40 Analiza.

def build_ficha_from_pack(pack: KnowledgePack) -> tuple[list[dict], dict, list[dict], list[dict], list[KnowledgeGap]]:
    """Devuelve (parametros_convocatoria, tres_ofertas, documentos_convocatoria,
    datos_aplicativo, gaps) — mismos cuatro bloques que _extract_ficha_convocatoria,
    construidos sin IA a partir de entidades 'limit' / 'procedural_rule' /
    'documentation' del pack. Solo se materializan entidades usables; el resto
    queda como gap."""
    gaps: list[KnowledgeGap] = []

    parametros_convocatoria = []
    for entity in pack.by_type("limit") + pack.by_type("procedural_rule"):
        if entity.is_canonical() or entity.is_usable_but_unvalidated():
            if not isinstance(entity.value, dict) or "valor" not in entity.value:
                gaps.append(KnowledgeGap(
                    codigo="(convocatoria)", kind="missing_entity_type", entity_type=entity.entity_type,
                    detail=f"Entidad '{entity.entity_id}' de tipo {entity.entity_type} sin 'valor' estructurado utilizable.",
                ))
                continue
            param = {
                "id": entity.entity_id,
                "label": entity.label,
                "valor": entity.value["valor"],
            }
            if entity.value.get("unidad"):
                param["unidad"] = entity.value["unidad"]
            nota_bits = []
            if entity.value.get("nota"):
                nota_bits.append(entity.value["nota"])
            if entity.review_state != "human_validated":
                nota_bits.append("Pendiente de validación humana en el Knowledge Pack.")
            if nota_bits:
                param["nota"] = " ".join(nota_bits)
            parametros_convocatoria.append(param)
        elif entity.is_missing():
            gaps.append(KnowledgeGap(
                codigo="(convocatoria)", kind="missing_entity_type", entity_type=entity.entity_type,
                detail=f"'{entity.label}' está en el pack pero como {entity.evidence_status} (desconocido, no ausente).",
            ))

    tres_ofertas = {"umbral": None, "exencion_gasto_antes_resolucion": False, "condiciones_exencion": ""}
    tres_ofertas_entities = [e for e in pack.entities if e.entity_id == "tres-ofertas" or e.entity_type == "procedural_rule" and "oferta" in e.label.lower()]
    to_entity = next((e for e in tres_ofertas_entities if e.is_canonical() or e.is_usable_but_unvalidated()), None)
    if to_entity and isinstance(to_entity.value, dict):
        tres_ofertas = {
            "umbral": to_entity.value.get("umbral"),
            "exencion_gasto_antes_resolucion": bool(to_entity.value.get("exencion_gasto_antes_resolucion", False)),
            "condiciones_exencion": to_entity.value.get("condiciones_exencion") or "",
        }
    else:
        gaps.append(KnowledgeGap(
            codigo="(convocatoria)", kind="no_match", entity_type="procedural_rule",
            detail="No hay entidad utilizable de 'tres ofertas' en el Knowledge Pack; tres_ofertas queda con los valores de escape del contrato.",
        ))

    documentos_convocatoria = []
    for entity in pack.by_type("documentation"):
        if not (entity.is_canonical() or entity.is_usable_but_unvalidated()):
            continue
        value = entity.value if isinstance(entity.value, dict) else {}
        documentos_convocatoria.append({
            "nombre": entity.label,
            "fuente": value.get("fuente") or "cliente",
            "obligatorio": bool(value.get("obligatorio", True)),
            **({"nota": value["nota"]} if value.get("nota") else {}),
        })

    datos_aplicativo: list[dict] = []  # el Knowledge Pack sintético de este caso no distingue
    # datos de aplicativo de la memoria narrativa; se deja vacío deliberadamente en vez de
    # inventar entradas — es un hueco real del pack de prueba, no una omisión de este módulo.

    return parametros_convocatoria, tres_ofertas, documentos_convocatoria, datos_aplicativo, gaps


# ---------------------------------------------------------------------------
# IDs estables para inputs (reutiliza el mecanismo del contrato v2.5, no crea otro)
# ---------------------------------------------------------------------------
#
# El contrato v2.5 ya resuelve esto: cada input lleva un "id" propio, distinto
# de "label" (texto de UI). La novedad de este módulo es solo CÓMO se deriva
# ese id cuando el label puede variar entre generaciones o entre KP y
# plantilla: a partir del entity_id del Knowledge Pack cuando el input
# proviene de una entidad normativa (estable por construcción), o de un slug
# determinista del concepto cuando no.

def stable_input_id(entity: NormativeEntity | None, fallback_label: str) -> str:
    if entity is not None:
        return entity.entity_id
    return _ascii_slug(fallback_label)


def _ascii_slug(value: str) -> str:
    value = (value or "").replace("ñ", "ni").replace("Ñ", "NI")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return ascii_text or "campo"


# ---------------------------------------------------------------------------
# Auditoría de procedencia por apartado (interna; nunca se envía a MemorAI)
# ---------------------------------------------------------------------------

@dataclass
class SectionProvenance:
    deliverable_section: str
    knowledge_refs: list[str] = field(default_factory=list)       # entity_id usados
    evidence_refs: list[dict] = field(default_factory=list)       # {entity_id, document_id, quote, section}
    knowledge_gaps: list[dict] = field(default_factory=list)
    conflicts_used: list[str] = field(default_factory=list)       # entity_id en conflicto que se mencionaron (nunca como hecho)
    unvalidated_knowledge_used: list[str] = field(default_factory=list)  # entity_id accredited-sin-validar usados

    def to_dict(self) -> dict:
        return {
            "deliverable_section": self.deliverable_section,
            "knowledge_refs": self.knowledge_refs,
            "evidence_refs": self.evidence_refs,
            "knowledge_gaps": self.knowledge_gaps,
            "conflicts_used": self.conflicts_used,
            "unvalidated_knowledge_used": self.unvalidated_knowledge_used,
        }


def build_section_provenance(section_match: SectionMatch, gaps: list[KnowledgeGap]) -> SectionProvenance:
    prov = SectionProvenance(deliverable_section=section_match.codigo)
    for entity in usable_entities(section_match):
        prov.knowledge_refs.append(entity.entity_id)
        for ref in entity.evidence_refs:
            prov.evidence_refs.append({
                "entity_id": entity.entity_id,
                "document_id": ref.document_id,
                "quote": ref.quote,
                "section": ref.section,
            })
        if entity.review_state != "human_validated":
            prov.unvalidated_knowledge_used.append(entity.entity_id)
    for entity in section_match.entities():
        if entity.is_conflict():
            prov.conflicts_used.append(entity.entity_id)
    prov.knowledge_gaps = [
        {"kind": g.kind, "entity_type": g.entity_type, "detail": g.detail} for g in gaps
    ]
    return prov
