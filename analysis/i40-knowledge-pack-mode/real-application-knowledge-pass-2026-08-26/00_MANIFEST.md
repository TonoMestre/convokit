# REAL CONVOKIT KNOWLEDGE PACK PASS — manifiesto reproducible

Prueba E2E: Knowledge Pack real de i40 Analiza (hosted, corpus real) →
`export_application_knowledge_pack`/`to_convokit_pack` (i40, código real de
`master`) → `knowledge_pack.parse_knowledge_pack` (ConvoKit) →
`_generate_output_4_kp` (ConvoKit, 18 apartados, IA real) →
`exporters.export_output_4` (v2.5) → `convokit_validator` (MemorAI).

Este documento es la fuente de verdad de "qué se probó, con qué datos, con
qué código y cuál fue el resultado" sin depender de ninguna conversación.

## Identificación

- **`analysis_id`** (i40 Analiza, `public.analyses`): `c5bb1aa0-20c3-4f65-8a95-62607622140a`
- **Convocatoria**: título `INPYME 2026`, `public_body` "Conselleria Industria", `call_year` 2026, `status` en el momento de la prueba: `evaluation_review`, `corpus_status`: `sufficient_with_reservations`
- **Fecha de exportación (UTC)**: `2026-08-26T09:06:24.223379+00:00`
- **Commit de i40 Analiza usado**: `b36a57799057a424a2a064533e3c81f5835d4ba5` (rama `master`). `export.py` verificado sin modificar en ese commit (diff vacío antes y después de la ejecución).
- **HEAD de ConvoKit en el momento de la prueba**: `950fccd` (rama `feature/i40-knowledge-pack-mode`)

## Artefactos conservados en este directorio

| Archivo | SHA-256 | Contenido |
|---|---|---|
| `01_inpyme2026_application_knowledge_real.json` | `8521117c0204fba23e318539d2ae6d4d1d062e55f79ac3c2b02828f2e993a2f1` | Pack nativo i40 (`export_application_knowledge_pack`): 6 `evaluation_block` + 17 `evaluation_criterion` + 23 `evaluation_subcriterion` = 46 entidades, `knowledge_gaps: []`, 7 documentos reales referenciados |
| `02_inpyme2026_convokit_pack_real.json` | `93679859f19e4a4431d8c50cc3f5264d80668859599409473715f3ff294fa06e` | Pack convertido (`to_convokit_pack`): 48 entidades ConvoKit — 22 `criterion`, 23 `subcriterion`, 2 `threshold`, 1 `exclusion` |
| `03_export_real_pack_readonly.py` | — (script, no dato) | Entrypoint de referencia para regenerar 01/02 desde hosted, solo lectura (ver cabecera del script para uso y garantías) |
| `00_MANIFEST.md` | este archivo | Resumen reproducible |

**Nota sobre reproducibilidad exacta del hash**: los dos artefactos JSON son
volcados deterministas de filas hosted (sin generación IA), así que
re-ejecutar `03_export_real_pack_readonly.py` contra las MISMAS filas
reproduce el MISMO contenido. El SHA-256 exacto depende también del
formato de serialización (indentación, orden de claves) del script que lo
produce — si al reproducirlo cambia el hash pero no los conteos/valores, es
un cambio de formato, no de datos.

## Qué NO se conserva aquí, y por qué

El markdown/JSON generado por Claude para los 18 apartados (redacción
narrativa real) **no se congela como fixture** en este directorio a
propósito: es contenido generativo, no dato determinista, y congelarlo
invitaría a que un test futuro esperase la misma redacción exacta de Claude
(prohibido explícitamente para esta prueba). Lo que SÍ se congela son los
**invariantes estructurales** del resultado (tabla más abajo) — ids, tipos,
scoring, ausencia de gaps, conteos de evidencia — que sí son deterministas
dado el mismo pack de entrada y el mismo código.

## Conteos verificados

- **46 entidades Application Knowledge** (nativo i40): 6 bloques / 17 criterios / 23 subcriterios, `knowledge_gaps: []`
- **48 entidades ConvoKit** (convertidas): 22 criterion / 23 subcriterion / 2 threshold / 1 exclusion
- **102 EvidenceRefs** totales tras `parse_knowledge_pack`, 0 pérdidas frente al pack de entrada, 0 entidades sin evidencia

### Distribución `entity_type` (nativo i40, hosted)

| tipo | filas |
|---|---|
| evaluation_block | 6 |
| evaluation_criterion | 17 |
| evaluation_subcriterion | 23 |

### Distribución `entity_type` (ConvoKit, convertido)

| tipo | entidades |
|---|---|
| criterion | 22 |
| subcriterion | 23 |
| threshold | 2 |
| exclusion | 1 |

### `scoring_status` (hosted, 46 filas)

| valor | filas | nota |
|---|---|---|
| scored | 40 | |
| not_scored | 1 | apartado "0" |
| `NULL` | 5 | filas históricas de II.B (migración 0053, anteriores a la columna `scoring_status` de la migración 0059) — bloque II + criterio II.B + 3 subcriterios |

### `is_exclusionary` (hosted, 46 filas): `True`=1 (apartado 0), `False`=45

### `rule_payload` (hosted, 46 filas): 8 con regla estructurada real (`score_by_bands`, `fixed_score_condition`), 38 sin regla estructurada (score_max escalar simple o sin score)

## Resultado del parser (ConvoKit)

`knowledge_pack.parse_knowledge_pack(pack_convertido)` → **48/48 aceptadas**,
0 `KnowledgePackError`, 0 pérdida de EvidenceRefs, 0 discrepancias de conteo
entrada→salida.

## Resultado de la generación — 18/18 apartados

| code | scoring_expectation | puntos_max | knowledge_gaps (apartado) |
|---|---|---|---|
| 0 | not_scored | `null` (nunca 0 — invariante verificado) | 0 |
| I.A | scored | 4 | 0 |
| I.B | scored | 1 | 0 |
| I.C | scored | 3 | 0 |
| II.A | scored | 6 | 0 |
| II.B | scored | 4 | 0 |
| II.C | scored | 40 | 0 |
| II.D | scored | 3 | 0 |
| II.E | scored | 2 | 0 |
| III.A | scored | 4 | 0 |
| III.B | scored | 4 | 0 |
| III.C | scored | 4 | 0 |
| IV.A | scored | 4 | 0 |
| IV.B | scored | 4 | 0 |
| IV.C | scored | 4 | 0 |
| V.A | scored | 2 | 0 |
| V.B | scored | 10 | 0 |
| V.C | scored | 1 | 0 |

**Gaps globales (nivel convocatoria, no apartado): 2** — `tres_ofertas` y
`convocatoria_metadata.tipo_ayuda`. Análisis de causa raíz de ambos en
`01_GAPS_ANALYSIS.md` de este directorio (fase B de la auditoría posterior a
esta prueba; no implementados, solo documentados).

### Corrección de formulación — apartado II.C

Una afirmación de una versión anterior (conversacional, nunca persistida en
ningún artefacto de este repositorio) decía incorrectamente "falta un 5º
subcriterio de presupuestos/facturas" para II.C. Eso no está demostrado. La
formulación correcta, verificada contra los datos hosted reales:

> El criterio II.C declara un máximo de 40 puntos, pero los cuatro
> componentes explícitamente publicados (hosted, `application_knowledge_entities`)
> suman 35 puntos (25 + 5 + 3 + 2). La revisión exhaustiva del corpus oficial
> disponible no permite identificar ni justificar los 5 puntos restantes.

No se ha modificado hosted ni se ha inventado un quinto componente.

## MemorAI v2.5

`convokit_validator.es_json_v2()` → `True` (sobre el JSON crudo y sobre el
exportado vía `exporters.export_output_4`). `convokit_validator.validar()` →
**0 errores** en ambos casos.

## Coste real y modelos utilizados

| modelo | llamadas | input tokens | output tokens | coste (EUR) |
|---|---|---|---|---|
| `claude-sonnet-4-6` | 19 | 260 216 | 26 459 | 1.083331 |
| `claude-haiku-4-5-20251001` | 20 | 115 380 | 36 062 | 0.217629 |
| **Total** | **39** | **375 596** | **62 521** | **1.30096 EUR (~1.41 USD)** |

Proveedor: API directa de Anthropic (`anthropic.Anthropic`), clave de
`backend/.env` de ConvoKit. Presupuesto autorizado: hasta 2 USD; coste real
dentro del presupuesto.

## Cómo reproducir (sin gastar IA de nuevo)

1. Los pasos 1-4 (verificación hosted + exportación real) se reproducen con
   `03_export_real_pack_readonly.py` de este directorio — solo lectura,
   sin IA, coste cero.
2. El paso 5 (parseo por ConvoKit) se reproduce con:
   ```
   python -c "import knowledge_pack as kp, json; print(len(kp.parse_knowledge_pack(json.load(open('02_inpyme2026_convokit_pack_real.json', encoding='utf-8'))).entities), 'entities OK')"
   ```
   ejecutado desde `backend/` de ConvoKit.
3. El paso 6 (generación de los 18 apartados) **sí** requiere IA real y no
   se debe repetir solo para verificar este resultado — los invariantes
   estructurales de la tabla de arriba ya están verificados y congelados
   aquí. Repetirlo solo tiene sentido si cambia el pack de entrada, el
   código de `_generate_output_4_kp`, o se quiere una nueva redacción.

## Disciplina de uso de este artefacto (no confundir con fixture/ground truth)

Este resultado **puede** usarse como referencia histórica/de regresión para:
IDs, tipos de entidad, `scoring_status`, `rule_payload`, conteo de
EvidenceRefs, ausencia de gaps conocidos, y estos hashes de entrada.

Este resultado **no debe** usarse para:
- hacer que un test futuro espere la redacción exacta de Claude para
  cualquier apartado;
- congelar interpretaciones generativas como si fueran normativa;
- asumir que un pack de entrada distinto (otra convocatoria, otra versión
  del pack de INPYME) debe producir gaps=2 o los mismos puntos_max — esos
  valores son correctos PARA ESTE pack de entrada exacto (hash arriba), no
  una propiedad universal del pipeline.
