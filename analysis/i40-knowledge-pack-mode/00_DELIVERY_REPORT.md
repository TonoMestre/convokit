# 00 — Informe de entrega: modo i40 Knowledge Pack para ConvoKit

Rama: `feature/i40-knowledge-pack-mode`. Sin merge. Base: `main` en el commit `d8fd811` de ConvoKit. MemorAI en `94dc15c` (solo lectura, cero cambios).

## 1. Hallazgo previo que condiciona todo lo demás

No existe hoy ningún `i40_knowledge_pack_sample.json` real de INPYME 2026 en el repositorio `i40 ANALIZA`. Se buscó exhaustivamente por nombre de fichero y por contenido (`knowledge_pack`, `EvidenceRef`, `evidence_status`, `application_knowledge`, "conocimiento normativo") en todo el repo. i40 Analiza hoy calcula el **Índice i40** de empresas/programas bajo la **Matriz i40** (52 criterios en 5 bloques: Necesidad, Diseño, Accesibilidad, Gestión, Impacto); no extrae baremos de convocatorias de ayudas para redacción de memorias. El único artefacto con "inpyme" en el nombre (`tests/fixtures/inpyme_expected.json`) es la regresión de esa metodología aplicada a INPYME **como programa a evaluar**, sin relación con el baremo de sus apartados.

Por tanto, la muestra de Knowledge Pack usada en el caso de prueba es **sintética**, construida por mí, dejando esto declarado dentro del propio fichero (clave `_disclaimer`). Reutiliza el vocabulario **real** de i40 Analiza donde existe (`entity_type` inspirado en su dominio, `evidence_status` copiado literalmente de `apps/web/src/lib/contracts/schemas/evidence-status.schema.json`, estructura de `EvidenceRef` de `evidence-ref.schema.json`) aplicado a hechos reales de INPYME 2026 ya verificados en el análisis de contrato previo (`analysis/convokit-memorai-contract-inpyme-2026/`), y es deliberadamente incompleta para que el test revele huecos reales, tal y como pide el punto 9 del encargo.

## 2. Arquitectura implementada

```
i40 Knowledge Pack (JSON)          plantilla de memoria (DOCX)
        │                          + Excel de costes (XLSX)
        │  parse_knowledge_pack            │  extractors.py (sin cambios)
        ▼                                  ▼
   NormativeEntity[]              estructura (codigo, nombre, orden)
        │                          SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP
        │                          (prohíbe extraer/mencionar puntuación)
        │                                  │
        └──────────► match_section_to_knowledge (determinista, sin IA) ◄──────┘
                              │
                    compute_knowledge_gaps (ANTES de generar)
                              │
              normative_context          deliverable_context
              (solo KP, usable)          (solo estructura)
                              │                  │
                        SECTION_PROMPT_SYSTEM_KP (Claude, un apartado)
                              │
                    OUTPUT_4_JSON_EXTRACTOR (sin cambios, Haiku)
                              │
        _consolidate_campos_empresa / _consolidate_campos_proyecto (sin cambios)
                              │
                build_ficha_from_pack (determinista, sin IA)
                              │
                    root v2.5 (IDÉNTICO contrato)
                              │
                exporters.export_output_4 (SIN MODIFICAR)
                              │
              MemorAI convokit_validator._upload_v2 (SIN MODIFICAR)
```

- **i40 Knowledge Pack** = fuente canónica de normativa. **Entregables** (plantilla, Excel) = fuente exclusiva de estructura. Nunca se mezclan como si fueran documentos equivalentes: van en bloques `NORMATIVE_CONTEXT` / `DELIVERABLE_CONTEXT` separados y marcados, y el propio system prompt instruye que un número visible en `DELIVERABLE_CONTEXT` ausente de `NORMATIVE_CONTEXT` "no existe" para esa llamada.
- **ConvoKit** sigue relacionando estructura↔normativa, decidiendo mínimo/completo, clasificando inputs, deduplicando campos, decidiendo los flags de rentabilidad/inversiones, diseñando el prompt y produciendo el JSON v2.5 completo — exactamente las responsabilidades que el encargo le asigna.
- **MemorAI** no se ha tocado ni conoce el Knowledge Pack: solo consume el JSON v2.5 resultante, con su validador real sin modificar.

## 3. Archivos modificados/creados

| Archivo | Tipo | Qué contiene |
|---|---|---|
| `backend/knowledge_pack.py` | nuevo | Modelo interno, parseo, matching determinista, gaps, ficha determinista, ids estables, auditoría |
| `backend/prompts.py` | modificado | + `SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP`, + `SECTION_PROMPT_SYSTEM_KP` (nada existente tocado) |
| `backend/main.py` | modificado | + `_generate_output_4_kp` (reutiliza 7 funciones existentes sin tocarlas) + 4 endpoints nuevos |
| `backend/tests/__init__.py`, `test_knowledge_pack.py`, `test_knowledge_pack_e2e.py` | nuevos | 24 tests, ver sección 5 |
| `CLAUDE.md` | modificado | Documentación del modo (sección "Modo i40 Knowledge Pack") |
| `analysis/i40-knowledge-pack-mode/*` | nuevo | Este informe y todos los artefactos del caso de prueba |

`git diff --stat main` (código, sin `analysis/`): 3 ficheros modificados (`CLAUDE.md`, `backend/main.py`, `backend/prompts.py`), 4 nuevos (`backend/knowledge_pack.py`, `backend/tests/{__init__,test_knowledge_pack,test_knowledge_pack_e2e}.py`), **1646 líneas añadidas, 0 eliminadas** — verificado con `git diff main -- backend/main.py backend/prompts.py`: cero líneas de código existente tocadas, todo lo añadido es inserción pura.

## 4. Tests añadidos y resultado

```
python -m unittest discover -s backend/tests -v
...
Ran 24 tests in 0.022s
OK
```

- `test_knowledge_pack.py` (20, unidad pura, sin red): parsing estricto, los cuatro estados (`human_validated` canónico / `accredited`+`unvalidated` usable-pero-marcado / `conflict` nunca categórico / `not_located` "desconocido" nunca "no existe" / `MISSING` nunca autorrellenado), matching semántico sin igualdad literal, "nunca inventa un id cuando no hay match", ids estables aunque cambie el label, auditoría de procedencia.
- `test_knowledge_pack_e2e.py` (4, integración con `main._claude` monkeypatcheado, sin red): documentos normativos prohibidos rechazados con HTTP 422 antes de la primera llamada; pipeline completo produce un objeto v2.5 real que pasa por `exporters.export_output_4` sin tocarlo; **el modo tradicional (`_generate_output_4`) sigue funcionando exactamente igual y no depende de nada de `knowledge_pack.py`**; el objeto generado en modo KP pasa el `convokit_validator.validar` **real** de MemorAI (import de solo lectura, se salta si el repo no está presente) con **cero errores**.

Cobertura de los 10 puntos pedidos: 1-9 cubiertos por los tests unitarios/e2e; el punto 10 (MemorAI acepta sin modificación) está cubierto tanto por el test automatizado como por la ejecución real de la sección 7.

## 5. Caso de prueba real: INPYME 2026 · i40 Knowledge Pack test

Convocatoria nueva e independiente: `convocatorias.id = 12` en `convokit.db`, nombre `INPYME 2026 · i40 Knowledge Pack test`. La convocatoria histórica (`id = 8`) no se ha tocado (verificado: sigue con sus 4 documentos originales).

Inputs cargados en la convocatoria 12:
1. `i40_knowledge_pack_sample_inpyme2026.SYNTHETIC.json` (25 entidades) vía `POST /convocatorias/12/knowledge-pack`.
2. `F88114.docx` (plantilla oficial de memoria) — texto reutilizado del ya extraído para la convocatoria histórica (mismos bytes que ConvoKit extraería del original; no se dispone del binario original en esta máquina).
3. `F96434.xlsx` (modelo de tabla de costes) — idem.

NO cargados: convocatoria/resolución, bases, guía de solicitud, resoluciones posteriores, portal GVA — verificado por código: `_generate_output_4_kp` rechaza con HTTP 422 si alguno de esos tipos está presente, y el test `test_prohibited_normative_documents_rejected_before_any_call` lo comprueba.

Ejecución: script directo (`main._generate_output_4_kp`, cliente Anthropic real, sin pasar por `uvicorn --reload` para evitar que una escritura concurrente cortara la ejecución larga a mitad — ver nota operativa en la sección 8). Duración: 963 segundos (~16 min). Resultado persistido en `convokit.db` bajo `entregables_json["4_kp"]` / `["4_kp_json"]` / `["4_kp_audit"]` de la convocatoria 12, y volcado a los ficheros de esta carpeta.

**Resultado**: 18 apartados generados — exactamente los 18 apartados reales de la memoria oficial (`0, I.A-C, II.A-E, III.A-C, IV.A-C, V.A-C`), **cero** apartados `TCE-*` inventados (la generación histórica v1.x había producido 4 de más a partir del Excel). 11 `knowledge_gaps` detectados en total.

## 6. Instrumentación de II.B

Ficheros:
- `01_INPYME_KP_IIB_SECTION.md` — bloque markdown tal cual lo redactó Claude.
- `02_INPYME_KP_IIB_RAW.json` — objeto JSON de II.B, salida cruda de `_generate_output_4_kp`.
- `07_INPYME_KP_IIB_EXPORTED.json` — el mismo apartado tras pasar por `exporters.export_output_4` sin modificar.

Resumen de lo pedido en el punto 9:

1. **Estructura de `F88114.docx`**: código `II.B`, nombre "Viabilidad económica de la inversión", extraídos por `SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP` — sin ninguna cifra de puntuación en la salida de ese paso (verificado: el JSON de estructura solo trae `{codigo, nombre}`).
2. **Conocimiento encontrado en el Knowledge Pack**: 3 entidades usables — `inpyme26-iib-criterion` (4 pt, `human_validated`), `inpyme26-iib-sub-ratio-rentabilidad` (2 pt, `human_validated`), `inpyme26-iib-sub-fuentes-financiacion` (1 pt, `accredited`/`unvalidated`, usada con nota de cautela).
3. **Conocimiento que usaba la generación histórica y ya no está disponible**: el subcriterio de pay-back (1 pt) — presente en el md histórico como hecho firme, ausente del Knowledge Pack sintético (`not_located`).
4. **`knowledge_gaps` de II.B**: uno, `entity_unknown` sobre `inpyme26-iib-sub-payback`, con el detalle exacto de qué falta y por qué (ver `05_INPYME_KP_AUDIT.json`, sección `"II.B"`).
5. **Inputs propuestos**: 6 — datos de empresa (1, consolidado con `ref_campo_empresa`), rentabilidad estructurada, inversión estructurada, fuentes de financiación (texto libre), documento bancario, hipótesis de ingresos/ahorro (texto libre). Sin duplicados de label entre modos mínimo/completo (arquitectura v2.5).
6. **Flags**: `requiere_calculo_rentabilidad: true`, `usa_tabla_inversiones: true` — coherentes con que el Knowledge Pack marca este apartado como el que valora rentabilidad.
7. **Prompt generado**: ver `01_INPYME_KP_IIB_SECTION.md`, bloque "INSTRUCCIÓN A CLAUDE". Menciona el hueco de pay-back explícitamente y pide marcarlo con `[DATO PENDIENTE]` si procede — **con una salvedad real, ver sección 9**.
8. **Objeto v2.5**: `02_INPYME_KP_IIB_RAW.json` (ver también `07_...EXPORTED.json` tras pasar por el exportador sin tocar).

## 7. Confirmación de aceptación por MemorAI (`_upload_v2`)

Ejecutado dos veces, ambas con éxito:
- Automatizado: `test_knowledge_pack_e2e.py::TestMemorAICompatibility` (objeto pequeño de prueba).
- **Sobre el objeto real de INPYME 2026 KP** (18 apartados, 20 campos_empresa, parámetros, documentos): 

```
es_json_v2: True
errores: []
VALIDO: True
```

usando `C:\Dev\MEMORAI\backend\app\services\convokit_validator.py` sin ninguna modificación (import de solo lectura desde un script de ConvoKit). `exporters.export_output_4` de ConvoKit tampoco se ha modificado: el objeto pasa por la misma función que usa cualquier convocatoria documental.

## 8. Comparación II.B: nuevo vs. histórico

Ver `08_COMPARISON_IIB_KP_VS_HISTORICO.md` para la tabla completa clasificada en `EXPECTED_IMPROVEMENT` / `EXPECTED_DUE_TO_KNOWLEDGE_GAP` / `REGRESSION` / `LEGACY_BUG_REMOVED`. Resumen:

- **Ninguna regresión detectada.**
- Los cuatro bugs legacy que el encargo pide no reproducir: **ninguno se reprodujo**. Tres de ellos (desajuste de labels, `fuente_inversiones` ausente, PEE afirmado sin estar adjunto) ya estaban resueltos por el contrato v2.5 en modo documental, no son mérito específico del modo Knowledge Pack — lo digo explícitamente para no atribuirme un mérito ajeno. El cuarto (apartados `TCE-*` inventados) sí lo corrige específicamente este modo: el extractor de estructura nuevo prohíbe tratar el Excel como apartado propio, y en la generación documental v1.x/histórica ese extractor no existía.
- Mejora real y verificada: la incertidumbre queda visible (fuentes de financiación marcadas "pendiente de validación humana", pay-back marcado `[DATO PENDIENTE]` con la razón exacta) en vez de presentarse con la misma seguridad que un hecho confirmado, que es justo lo que hacía la generación histórica.

## 9. Limitaciones encontradas

**Del mecanismo (descubierta en la ejecución real, no en el diseño):** el system prompt prohíbe expresamente extraer o mencionar un número de puntuación que solo esté en `DELIVERABLE_CONTEXT`. En la ejecución real, el modelo respetó la prohibición como *hecho firme* (nunca declaró "el pay-back vale 1 punto" sin matiz), pero dentro de la INSTRUCCIÓN A CLAUDE sí mencionó la cifra con una salvedad explícita ("hasta 1 punto, aunque el Knowledge Pack no confirma este peso de forma explícita"). Es un cumplimiento en espíritu, no literal, de la regla — mejor que la generación histórica (que la presentaba sin ninguna salvedad) pero no perfecto. Vía de mejora futura no implementada aquí por alcance: redactar `DELIVERABLE_CONTEXT` de forma determinista antes de enviarlo (enmascarar patrones tipo "(máx. N puntos)") en vez de confiar solo en la instrucción.

**De `compute_knowledge_gaps` (documentada también en `CLAUDE.md`):** `expects_scoring` se pasa siempre en `True`. Saber si un apartado puntúa es en sí mismo conocimiento normativo y no puede derivarse de la estructura del entregable sin arriesgar la reinterpretación que el punto 4 del encargo prohíbe; el efecto práctico es que apartados genuinamente sin baremo podrían señalar un `missing_entity_type: criterion` que no aplica. No se ha resuelto a propósito.

**Del Knowledge Pack de prueba (sintético, esperado):** cubre bien II.B pero deja huecos deliberados en `0`, `I.C`, `III.B`, `III.C` (sin `criterion` localizado) y `V.B` (conflicto sin resolver, dos valores de puntuación sin conciliar); `tres_ofertas` no tiene ninguna entidad `accredited` (solo una `inferred` de baja confianza, correctamente descartada); solo 2 `parametros_convocatoria` y 1 `documentos_convocatoria`, frente a los que tendría una convocatoria completamente cubierta.

**Del alcance de esta entrega:** no se ha construido UI de frontend para subir el Knowledge Pack ni para lanzar la generación en este modo (los endpoints están completos y probados, pero el flujo hoy se opera por API/script, no desde `EntregablePanel.jsx`). Es una elección deliberada de alcance dado que el encargo pedía arquitectura, contrato y caso de prueba verificable, no una superficie de usuario nueva; lo dejo explícito para que se decida si hace falta en una siguiente iteración.

**Operativa (no del feature):** el script de ejecución directa (`run_kp_generation.py`, en el scratchpad de la sesión, no en el repo) no pasó `_track` a `_generate_output_4_kp`, así que el coste de la ejecución real de 963 s no quedó registrado en `api_calls`. Los endpoints HTTP (`POST /generate/kp`) sí lo hacen correctamente (`_make_tracker`), es un detalle del script ad-hoc de validación, no del código entregado.

## 10. Confirmaciones

- **0 cambios en MemorAI**: `git -C C:\Dev\MEMORAI status --short` no muestra ninguna modificación atribuible a este trabajo (los `.pyc` y temporales de Vite listados son preexistentes, verificado por fecha).
- **0 cambios en el contrato de salida v2.5**: `exporters.export_output_4` y `convokit_validator.py` de MemorAI no se han tocado; el objeto generado en modo KP pasa por ambos sin modificarlos y sin errores.
- **No merge**: todo el trabajo vive en `feature/i40-knowledge-pack-mode`; `main` no se ha tocado.
- **Convocatoria histórica intacta**: `convocatorias.id=8` sigue con sus 4 documentos originales, verificado tras la ejecución.
